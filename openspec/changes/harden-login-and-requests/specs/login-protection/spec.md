# Spec Delta

## Purpose

Defines how sign-in is defended against password guessing and abuse: which failed attempts are counted together, which address counts as the client's, how large sign-in input may be, how old records are cleaned up, and how the sign-in cookie is named.

## ADDED Requirements

### Requirement: Throttling keyed by email and client address
The system SHALL refuse further sign-in attempts, even with the correct password, when any of these limits is reached within 10 minutes: 5 failures for the same email from the same client address; 30 failures for the same email from any addresses; 20 failures from the same client address for any emails. A throttled user SHALL see a clear "try again later" message.

#### Scenario: A stranger cannot block the real user
- **WHEN** someone fails to sign in as a user 5 times from one address and the real user then signs in with the correct password from a different address
- **THEN** the real user is signed in

#### Scenario: Repeated failures from one address
- **WHEN** 5 sign-in attempts for one email fail from one address within 10 minutes
- **THEN** the sixth attempt from that address for that email is refused, even with the correct password

#### Scenario: Guessing from many addresses
- **WHEN** 30 sign-in attempts for one email have failed within 10 minutes from several addresses
- **THEN** further attempts for that email are refused from every address until the window passes

#### Scenario: Many emails from one address
- **WHEN** 20 sign-in attempts have failed from one address within 10 minutes, for any emails
- **THEN** further attempts from that address are refused

### Requirement: Failure accounting
The system SHALL count failed sign-in attempts for emails that do not belong to any user in the same way as for emails that do, so throttling reveals nothing about which emails exist. A refused attempt SHALL NOT count as another failure. A successful sign-in SHALL clear the failures of that email from that address only.

#### Scenario: Unknown emails look the same
- **WHEN** failed attempts are made for an email that has no user
- **THEN** throttling and the messages shown are the same as for an email that has a user

#### Scenario: Success clears only its own failures
- **WHEN** a user signs in successfully after earlier failures
- **THEN** the failures of that email from that address no longer count, and failures from other addresses still do

#### Scenario: Refused attempts are not counted again
- **WHEN** an attempt is refused because of throttling
- **THEN** no new failure is recorded, so the cooling-off period does not extend itself

### Requirement: Client address behind a trusted proxy
The system SHALL use the address of the connection as the client address, unless it is configured to run behind exactly one trusted proxy. Behind the trusted proxy it SHALL use the last entry of the `X-Forwarded-For` header, the one the proxy added itself, and SHALL ignore any entries before it. A missing or empty header SHALL fall back to the address of the connection.

#### Scenario: Forged forwarding header
- **WHEN** the proxy is trusted and a client sends its own `X-Forwarded-For` header with invented addresses
- **THEN** the throttling counts the client under the address the proxy appended, so inventing addresses does not avoid it

#### Scenario: No trusted proxy
- **WHEN** the proxy setting is off and a request carries an `X-Forwarded-For` header
- **THEN** the header is ignored

### Requirement: Limits on sign-in input
The system SHALL refuse a sign-in request whose email is longer than 320 characters or whose password is longer than 1024 characters with a validation error, before any password is hashed. Such a request SHALL NOT be recorded as a failed attempt.

#### Scenario: Oversized email
- **WHEN** a sign-in request carries an email longer than 320 characters
- **THEN** the response is a validation error and nothing is stored about it

#### Scenario: Oversized password
- **WHEN** a sign-in request carries a password longer than 1024 characters
- **THEN** the response is a validation error and no password hash is computed

### Requirement: Old records are removed
The system SHALL remove failed-attempt records older than the throttling window and sessions that have expired, so these records cannot grow without bound. The clean-up SHALL run while the app is in use and SHALL NOT need a separate scheduled job.

#### Scenario: Old failed attempts
- **WHEN** a sign-in is processed after failed-attempt records have passed the 10-minute window
- **THEN** those records are removed

#### Scenario: Expired sessions
- **WHEN** a sign-in is processed after sessions have expired
- **THEN** the expired sessions are removed

### Requirement: Host-locked session cookie
The system SHALL name the sign-in cookie with the `__Host-` prefix whenever the cookie is restricted to HTTPS, so browsers only accept it from the exact host over HTTPS and never from a subdomain. When the cookie is not restricted to HTTPS (local development), it SHALL use a plain name. After a successful sign-in, the system SHALL remove any cookie that an earlier version of the app set under the old name. A request that carries only the old cookie SHALL be treated as not signed in.

#### Scenario: Secure deployment
- **WHEN** a user signs in while the cookie is restricted to HTTPS
- **THEN** the cookie is set under the `__Host-` name, with the secure, HTTP-only, same-site and path `/` attributes and no domain

#### Scenario: Local development
- **WHEN** a user signs in over plain http with the cookie not restricted to HTTPS
- **THEN** the cookie is set under a plain name and sign-in works

#### Scenario: Cookie from before the change
- **WHEN** a browser still holds the old-named cookie
- **THEN** the user is asked to sign in, and the old cookie is removed after they do
