# Spec Delta

## Purpose

Defines how a confirmed contact is written to FundraisingBox using the schema the FundraisingBox API documents: one person (or company) record plus separate address, phone, email and website records, checked before anything is created and resumable when a later step fails.

## ADDED Requirements

### Requirement: Contact details are separate records
The system SHALL store a contact's email, phone, mobile number, address and website as their own FundraisingBox records, each linked to the created person by its identifier, and SHALL NOT write these values into the person's info text. It SHALL create at most one email, one address and one website, and up to two phone records.

#### Scenario: Full card
- **WHEN** a contact with email, phone, mobile, street, postal code, city, country and website is sent
- **THEN** one person is created, followed by one email, two phone, one address and one website record, each linked to that person

#### Scenario: Missing values are skipped
- **WHEN** the contact has no website and no mobile number
- **THEN** no website record and no second phone record is created

#### Scenario: Details not in info
- **WHEN** any contact is sent
- **THEN** the person's info text contains no email, phone, mobile, address or website line

### Requirement: Type and main flags
The system SHALL create every email, address, website and phone record with the type `work`, except the mobile number, which SHALL use the type `other` because the create call has no mobile type, and SHALL mark the first record of each kind as the main one.

#### Scenario: Types
- **WHEN** a contact with phone and mobile is sent
- **THEN** the phone record has type `work` and the mobile record has type `other`

#### Scenario: Main record
- **WHEN** a contact with a phone and a mobile number is sent
- **THEN** the phone record is the main phone and the mobile record is not

### Requirement: Info text content
The system SHALL use the person's info text only for what has no field of its own: the card's notes, the company name when the person is not linked to a company record, and the country text when it cannot be turned into a country code.

#### Scenario: Notes
- **WHEN** the contact has notes
- **THEN** the info text contains them

#### Scenario: Unlinked company
- **WHEN** the person is not linked to a company record and the contact names a company
- **THEN** the info text names the company

#### Scenario: Nothing to note
- **WHEN** the contact has no notes, the person is linked to a company and the country is a known one
- **THEN** no info text is sent

### Requirement: Country codes
The system SHALL send the country of an address as the 2-letter code the API requires. It SHALL accept a 2-letter code as given and SHALL convert common German and English country names. It SHALL send an address whose country it cannot convert without a country and record the original text in the info text.

#### Scenario: Country name
- **WHEN** the contact's country is "Deutschland" or "Germany"
- **THEN** the address carries the country code `DE`

#### Scenario: Unknown country text
- **WHEN** the country text matches no known country
- **THEN** the address is created without a country and the info text contains the original text

### Requirement: Checked before anything is created
The system SHALL check every value against the API's documented limits before the first record is created, and SHALL refuse the whole send with a validation error that names each field and its limit when any value is too long. Nothing SHALL be created in that case.

#### Scenario: Field too long
- **WHEN** the email is longer than 100 characters, a phone number longer than 50, or the info text longer than 1000
- **THEN** the send is refused naming the field and its limit, and no record is created

#### Scenario: Several problems
- **WHEN** two fields are too long
- **THEN** both are named in the same answer

### Requirement: Person fields as documented
The system SHALL create the person with the documented fields only: last name, and when present first name, salutation (`Mr.`, `Mrs.`, `diverse`, `couple`, `family`), title, position, the company link and the info text. It SHALL set the ContactPilot custom field with the integer id 16786 and the value "Sync" on every person.

#### Scenario: Custom field
- **WHEN** a person is created
- **THEN** the request carries the custom field with id 16786 as a number and value "Sync"

#### Scenario: Unknown salutation
- **WHEN** the contact's salutation is not one the API accepts
- **THEN** no salutation is sent

### Requirement: Company-only cards
The system SHALL, for a card with only a company name, attach the contact details to the created company record, and SHALL cut the company record's required last name to the documented 100 characters while sending the full name as the company name.

#### Scenario: Company with details
- **WHEN** a company-only card with an email and a website is sent
- **THEN** the company record is created and the email and website records are linked to it

#### Scenario: Long company name
- **WHEN** the company name is longer than 100 characters
- **THEN** the company's last name is cut to 100 characters and its company name is complete

### Requirement: Resuming a partly failed send
The system SHALL, when the person was created but a later record fails, keep the contact open, tell the user that the person exists and which details are missing, and on retry create only the missing records and never a second person. The contact SHALL count as sent only when every record exists.

#### Scenario: Failure after the person
- **WHEN** the person is created and the phone record is rejected
- **THEN** the user is told the person exists and the phone is missing, and the contact is not marked as sent

#### Scenario: Retry
- **WHEN** the user retries after such a failure
- **THEN** only the records that were not created are sent, linked to the existing person

#### Scenario: Retry after a corrected value
- **WHEN** the user corrects the rejected phone number and retries
- **THEN** the corrected number is sent and the records already created are not sent again

### Requirement: Mock mode uses the same calls
The system SHALL, in mock mode, build and validate exactly the same person and child records and show every one of them in the done-screen preview, and SHALL NOT contact FundraisingBox.

#### Scenario: Preview
- **WHEN** a contact is sent in mock mode
- **THEN** the preview lists the person and each email, phone, address and website record that would have been created

#### Scenario: Same refusals
- **WHEN** a value that live mode refuses is sent in mock mode
- **THEN** it is refused in the same way and nothing is recorded
