# Spec Delta

## Purpose

Lets the whole scan, review and send flow run against an in-memory stand-in for FundraisingBox, so
the app can be demonstrated and tested end to end without touching real data.

## ADDED Requirements

### Requirement: Selectable FundraisingBox mode
The system SHALL read the setting `FUNDRAISINGBOX_MODE` with the values `live` and `mock`, SHALL treat a missing value as `live`, and SHALL refuse to start serving with a clear configuration error for any other value.

#### Scenario: Default is live
- **WHEN** `FUNDRAISINGBOX_MODE` is not set
- **THEN** the app behaves exactly as before and needs the FundraisingBox token

#### Scenario: Mock selected
- **WHEN** `FUNDRAISINGBOX_MODE` is `mock`
- **THEN** the app uses the in-memory stand-in for every FundraisingBox operation

#### Scenario: Invalid value
- **WHEN** `FUNDRAISINGBOX_MODE` has any other value
- **THEN** the app reports a configuration error that names the setting and the allowed values

### Requirement: Nothing is sent in mock mode
The system SHALL NOT make any request to FundraisingBox while in mock mode, and SHALL NOT require the FundraisingBox API token.

#### Scenario: Full flow without a token
- **WHEN** the app runs in mock mode with no token and a card is scanned, reviewed and sent
- **THEN** the send succeeds and no network request is made to FundraisingBox

#### Scenario: Health without a token
- **WHEN** the app runs in mock mode without a token and is otherwise configured
- **THEN** the health check reports healthy

### Requirement: The mock behaves like FundraisingBox for the flow
The system SHALL, in mock mode, answer company searches from a small built-in list plus companies created since the server started, SHALL return a new identifier for each created company or person, and SHALL apply the same field mapping and validation as in live mode.

#### Scenario: Searching finds the example companies
- **WHEN** the user searches for part of the name of a built-in example company, in any letter case
- **THEN** that company is offered as a match

#### Scenario: A created company is found afterwards
- **WHEN** a company is created in mock mode and the same name is searched again
- **THEN** the new company is offered as a match

#### Scenario: Same rules as live
- **WHEN** a contact that live mode would refuse, such as one whose notes make the info text too long, is sent in mock mode
- **THEN** it is refused in the same way and nothing is recorded

#### Scenario: Identifiers differ per record
- **WHEN** two contacts are sent in mock mode
- **THEN** each gets a different identifier

### Requirement: Mock mode is clearly marked
The system SHALL make mock mode visible on every signed-in page, on the done screen, in the health check and in the startup log, so that nobody can mistake mock records for saved ones.

#### Scenario: Notice on every page
- **WHEN** a signed-in user opens any page in mock mode
- **THEN** a notice states that nothing is sent to FundraisingBox

#### Scenario: Done screen wording
- **WHEN** a contact is sent in mock mode
- **THEN** the done screen says it was not sent to FundraisingBox and shows that it was a demo record

#### Scenario: Health and log
- **WHEN** the app runs in mock mode
- **THEN** the health response says `mock` and the startup log contains a warning that FundraisingBox is mocked

#### Scenario: No notice in live mode
- **WHEN** the app runs in live mode
- **THEN** no mock notice is shown anywhere

### Requirement: Payload preview
The system SHALL, in mock mode only, show on the done screen the data that would have been sent to FundraisingBox for the record, and SHALL discard it with the review session.

#### Scenario: Preview after a send
- **WHEN** a contact is sent in mock mode
- **THEN** the done screen offers to show the fields that would have been sent, including the info text and the ContactPilot custom field

#### Scenario: No preview in live mode
- **WHEN** a contact is sent in live mode
- **THEN** no payload is returned or shown

#### Scenario: Preview is not kept
- **WHEN** the review session has ended or the server has restarted
- **THEN** the preview is no longer available

### Requirement: Mock mode is only a configuration choice
The system SHALL switch between live and mock only through the server's configuration, never through a request, a setting stored in the database or anything a signed-in user can change.

#### Scenario: Users cannot switch modes
- **WHEN** a signed-in administrator uses any part of the app
- **THEN** there is no way to change the mode from within the app
