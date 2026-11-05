# Spec Delta

## Purpose

Defines how a reviewer records newsletter and contact-method consent for a contact on the review page and how that choice is written to FundraisingBox.

## ADDED Requirements

### Requirement: Review page offers communication options
The review page SHALL offer a Communication section with four independent options (newsletter, contact by email, contact by phone, contact by post), all unselected when a contact is first shown and never filled in from the card.

#### Scenario: Options start unselected
- **WHEN** a scanned card is shown on the review page
- **THEN** all four options are unselected, whatever the card contains

#### Scenario: Options are accessible
- **WHEN** a person uses only the keyboard and a screen reader
- **THEN** each option is a labelled checkbox in a labelled group and can be toggled

### Requirement: Chosen options are sent with the contact
The send SHALL carry the chosen options with the confirmed contact, and a selected option SHALL be written to the new FundraisingBox record as consent, while an unselected option SHALL send nothing so the FundraisingBox default remains.

#### Scenario: Newsletter selected
- **WHEN** the reviewer selects the newsletter and sends
- **THEN** the person is created with the newsletter flag set to true

#### Scenario: Contact method selected
- **WHEN** the reviewer selects contact by phone and sends
- **THEN** the person is created with the no-call flag set to false and no other contact flag is sent

#### Scenario: Nothing selected
- **WHEN** the reviewer selects no option and sends
- **THEN** no newsletter or contact flag is sent

### Requirement: Mock preview shows the flags
In mock mode the preview of what would have been sent SHALL include the newsletter and contact flags exactly as they would be sent.

#### Scenario: Preview with options
- **WHEN** a contact is sent in mock mode with the newsletter selected
- **THEN** the preview of the person shows the newsletter flag as true

### Requirement: A resumed send does not silently drop a changed choice
When a send failed part way and the person already exists, the failure message SHALL say that changes to the communication options are not applied to the existing record.

#### Scenario: Choice changed after a partial failure
- **WHEN** a detail step failed, the reviewer changes the newsletter option and sends again
- **THEN** the person is not created again and the message names the options among the changes not applied
