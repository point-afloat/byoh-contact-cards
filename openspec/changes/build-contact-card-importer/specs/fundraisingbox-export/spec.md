# Spec Delta

## Purpose

Sends a reviewed and confirmed contact to FundraisingBox as a person record through its API and reports the outcome reliably to the user.

## ADDED Requirements

### Requirement: Create person in FundraisingBox
The system SHALL create a FundraisingBox person from the confirmed contact by POSTing to the FundraisingBox persons API authenticated with the configured API token.

#### Scenario: Successful send
- **WHEN** the user confirms a valid contact
- **THEN** the system creates the person in FundraisingBox and shows a success message including the created person's identifier

### Requirement: Field mapping
The system SHALL map contact fields to FundraisingBox person fields (salutation, title, first name, last name, position, company name or company id) and SHALL set the ContactPilot custom field (id 16786, name "ContactPilot") to the value "Sync" on every created person, exactly as the prototype does.

#### Scenario: Company link used
- **WHEN** the user linked the contact to an existing FundraisingBox company
- **THEN** the person is created with that company's id and without conflicting identity fields that the account does not allow to be edited

#### Scenario: ContactPilot custom field
- **WHEN** any person is created
- **THEN** the request includes the custom field with id 16786, name "ContactPilot" and value "Sync"

### Requirement: Contact channel data preserved
The system SHALL ensure email, phone, mobile, address, and website values from the card are not silently dropped, by recording them as labelled lines in the person's info text within the same request that creates the person.

#### Scenario: Email and phone on card
- **WHEN** the confirmed contact has an email and a phone number
- **THEN** both values are present in the info text of the person stored in FundraisingBox

#### Scenario: Info text too long
- **WHEN** the combined channel data would exceed the FundraisingBox info length limit
- **THEN** the system blocks sending, tells the user how much to shorten, and creates nothing

### Requirement: Create missing company
The system SHALL, when the user chose to create a company that does not exist in FundraisingBox, create the company record first and then create the person linked to it, and SHALL reuse an already created company when the user retries after a later failure.

#### Scenario: Company and person created
- **WHEN** the user confirms a contact with a company that has no match and chose to create it
- **THEN** the company record is created first and the person is created linked to that company

#### Scenario: Person creation fails after company creation
- **WHEN** the company was created but creating the person fails
- **THEN** the user sees the failure and a retry creates only the person, linked to the already created company

### Requirement: Company-only submission
The system SHALL, for a card with only a company name, create just the company record when the user confirms, and SHALL NOT create a person.

#### Scenario: Company-only card confirmed
- **WHEN** the user confirms creating a company from a card without a person name
- **THEN** one company record is created and no person is created

### Requirement: Error reporting and retry
The system SHALL show the user the failure reason when FundraisingBox is unreachable or rejects a request, keep the reviewed data available, and allow the user to correct and resend.

#### Scenario: API rejects request
- **WHEN** FundraisingBox responds with an error status
- **THEN** the user sees the status and message, the review form keeps its values, and the user can resend

#### Scenario: API unreachable
- **WHEN** the request to FundraisingBox times out or cannot connect
- **THEN** the user sees a network error and can retry without re-uploading the card

### Requirement: Duplicate submission protection
The system SHALL prevent the same confirmed contact from being sent more than once through repeated clicks or a page reload after a successful send.

#### Scenario: Double click
- **WHEN** the user triggers send twice in quick succession for the same review session
- **THEN** only one person is created in FundraisingBox

#### Scenario: Resend after success
- **WHEN** a contact has already been sent successfully
- **THEN** the send action is disabled and the user is offered to scan the next card

### Requirement: Credential handling
The system SHALL read the FundraisingBox API token from configuration, SHALL fail with a clear message if it is missing, and SHALL NOT expose the token to the browser or logs.

#### Scenario: Token missing
- **WHEN** the token is not configured and the user tries to send
- **THEN** the user sees a configuration error and no request is made to FundraisingBox
