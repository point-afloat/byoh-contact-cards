# Spec Delta

## Purpose

Defines protections that apply to every request no matter who sends it: how large a request may be, which security headers every response carries, how often one user may start card uploads, and what the server says at startup when its cookie setting is unsafe.

## ADDED Requirements

### Requirement: Request body size limits
The system SHALL refuse a request body that is larger than the limit for its route, without reading or parsing it further, whether or not the sender is signed in. The limit for card uploads SHALL be the configured maximum upload size plus a small allowance for the multipart envelope. The limit for every other route SHALL be 64 KB. A refused request SHALL receive a 413 response with the usual `{code, message}` body.

#### Scenario: Anonymous oversized upload
- **WHEN** a request without a sign-in cookie posts a multipart body larger than the upload limit to the card upload route
- **THEN** the response is 413 and the body is never parsed

#### Scenario: Declared size is too large
- **WHEN** a request declares a content length above the limit for its route
- **THEN** the response is 413 before any of the body is read

#### Scenario: Streamed body without a declared size
- **WHEN** a request sends its body in chunks without a content length and the total passes the limit
- **THEN** reading stops at the limit and the response is 413

#### Scenario: Oversized JSON
- **WHEN** a request with a JSON body larger than 64 KB is sent to any route other than the card upload
- **THEN** the response is 413

#### Scenario: Upload at the limit
- **WHEN** a signed-in user uploads a card image whose size is exactly the configured maximum
- **THEN** the upload is accepted and processed as before

#### Scenario: Invalid content length
- **WHEN** a request carries a content length that is not a whole number
- **THEN** the response is 400 and the body is not read

### Requirement: Security response headers
The system SHALL send these headers on every response: a content security policy that allows only the app's own scripts, styles, images (including images created in the browser) and connections, and forbids framing, plugins and changes to the page's base address; `X-Content-Type-Options: nosniff`; `Referrer-Policy: no-referrer`; and `X-Frame-Options: DENY`.

#### Scenario: Headers on a page and on an API response
- **WHEN** the app's start page and any API route are requested
- **THEN** both responses carry the content security policy, `nosniff`, `no-referrer` and the frame protection headers

#### Scenario: The app still works under the policy
- **WHEN** the built app is opened in a real browser and a card is uploaded, reviewed and sent
- **THEN** the browser reports no content security policy violation

### Requirement: Transport security and caching headers
When the sign-in cookie is restricted to HTTPS, the system SHALL send a `Strict-Transport-Security` header on every response. Responses from routes under `/api` SHALL carry `Cache-Control: no-store`, because they hold names and card data.

#### Scenario: API responses are not cached
- **WHEN** any route under `/api` responds
- **THEN** the response carries `Cache-Control: no-store`

#### Scenario: Strict transport security follows the cookie setting
- **WHEN** the sign-in cookie is restricted to HTTPS
- **THEN** responses carry `Strict-Transport-Security`
- **AND** when it is not restricted, they do not

### Requirement: Limit on card uploads per user
The system SHALL limit how many card uploads one signed-in user can start per hour, because each upload is a paid call to the extraction model. The default limit SHALL be 120 uploads per hour and SHALL be configurable. A user over the limit SHALL receive a 429 response with a message that says when to try again, and the upload SHALL NOT be sent to the model. Uploads by other users SHALL NOT be affected.

#### Scenario: Over the limit
- **WHEN** a user has started as many uploads in the last hour as the limit allows and starts another
- **THEN** the response is 429 with a "try again later" message and no model call is made

#### Scenario: Another user is not affected
- **WHEN** one user is over the limit
- **THEN** another signed-in user can still upload

#### Scenario: Limit applies again after the window
- **WHEN** an hour has passed since the user's earlier uploads
- **THEN** the user can upload again

#### Scenario: Rejected files do not use up the allowance
- **WHEN** a user uploads a file that is refused as too large, unsupported or unreadable
- **THEN** that upload does not count towards the limit

### Requirement: Warning for an insecure cookie setting
The system SHALL write a warning to its log at startup when the sign-in cookie is not restricted to HTTPS, stating that this is only meant for local development. The warning SHALL NOT stop the app from starting and SHALL NOT appear in the public health response.

#### Scenario: Insecure cookie setting
- **WHEN** the app starts with the sign-in cookie not restricted to HTTPS
- **THEN** the log contains a warning that names the setting

#### Scenario: Secure cookie setting
- **WHEN** the app starts with the sign-in cookie restricted to HTTPS
- **THEN** no such warning is logged
