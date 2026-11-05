# user-authentication Specification

## Purpose
Restricts the application to signed-in, active users and defines how people sign in, stay signed in, change their password, and sign out.

## Requirements

### Requirement: Sign in with email and password
The system SHALL let an active user sign in with their email address and password and SHALL reject invalid combinations with a message that does not reveal whether the email exists.

#### Scenario: Valid credentials
- **WHEN** an active user submits the correct email and password
- **THEN** they are signed in and taken to the scan screen

#### Scenario: Invalid credentials
- **WHEN** a wrong password or unknown email is submitted
- **THEN** the system shows the same generic "email or password incorrect" message in both cases

#### Scenario: Deactivated user
- **WHEN** a deactivated user submits correct credentials
- **THEN** sign-in is refused with the generic message

### Requirement: Protected application and API
The system SHALL require a signed-in user for every page and API route except the sign-in page, invite acceptance, and the health check, and SHALL answer unauthenticated API requests with a 401 response and no data.

#### Scenario: Anonymous visitor
- **WHEN** a visitor without a session opens the app
- **THEN** they are shown the sign-in page and no card or contact data is served

#### Scenario: Anonymous API call
- **WHEN** an API request without a valid session is made to a protected route
- **THEN** the response is 401 and the request has no side effects

#### Scenario: Health check
- **WHEN** the platform requests the health check without credentials
- **THEN** it receives a 2xx response without any user or card data

### Requirement: Session lifetime and revocation
The system SHALL keep users signed in across browser restarts for a configured period, SHALL expire idle sessions after a configured time, and SHALL end a user's sessions immediately when the user is deactivated or their password is changed or reset.

#### Scenario: Deactivation ends sessions
- **WHEN** an admin deactivates a signed-in user
- **THEN** that user's next request returns 401 and they are shown the sign-in page

#### Scenario: Password change ends other sessions
- **WHEN** a user changes their password
- **THEN** their other sessions are ended and the current session stays signed in

### Requirement: Sign out
The system SHALL let a signed-in user sign out, which ends that session.

#### Scenario: Sign out
- **WHEN** the user chooses sign out
- **THEN** the session is ended and protected routes require sign-in again

### Requirement: Change own password
The system SHALL let a signed-in user change their password after entering their current password, and SHALL enforce a minimum length of 12 characters.

#### Scenario: Successful change
- **WHEN** the user enters the correct current password and a valid new password
- **THEN** the password is changed and a confirmation is shown

#### Scenario: Wrong current password
- **WHEN** the current password is incorrect
- **THEN** the password is not changed and an error is shown

### Requirement: Login throttling
The system SHALL slow or temporarily block repeated failed sign-in attempts for the same email or client, and SHALL show a clear "try again later" message.

#### Scenario: Repeated failures
- **WHEN** more than 5 failed attempts occur for one email within 10 minutes
- **THEN** further attempts are refused for a cooling-off period, even with the correct password

### Requirement: Secure credential and cookie handling
The system SHALL store passwords only as salted, slow hashes, SHALL keep session identifiers in HTTP-only, secure, same-site cookies, and SHALL NOT write passwords, tokens, or session identifiers to logs.

#### Scenario: Database inspection
- **WHEN** the user database is inspected
- **THEN** no plaintext passwords or usable invite/reset tokens are present

### Requirement: Bootstrap of the first admin
The system SHALL create an initial admin account from deployment configuration when no users exist, and SHALL ignore that configuration once any user exists.

#### Scenario: Empty database
- **WHEN** the app starts with no users and initial admin settings are configured
- **THEN** an admin with that email can sign in with the configured password

#### Scenario: Users already exist
- **WHEN** the app restarts with existing users and the initial admin settings are still configured
- **THEN** no account is created or changed

#### Scenario: Nothing configured
- **WHEN** the app starts with no users and no initial admin settings
- **THEN** it reports a clear configuration error and the health check fails
