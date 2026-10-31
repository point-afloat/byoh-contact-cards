# Spec Delta

## Purpose

Gives a person the chance to verify and correct extracted contact data against the original card, and to choose a matching FundraisingBox company, before anything is sent.

## ADDED Requirements

### Requirement: Side-by-side review
The system SHALL show the original card image next to an editable form containing every extracted field.

#### Scenario: Review after extraction
- **WHEN** extraction finishes
- **THEN** the user sees the card image and a form pre-filled with the extracted values, all editable

### Requirement: Mandatory confirmation
The system SHALL NOT send any contact to FundraisingBox until the user explicitly confirms the reviewed data.

#### Scenario: Nothing sent automatically
- **WHEN** extraction completes
- **THEN** no request is made to FundraisingBox until the user presses the confirm/send action

### Requirement: Field validation
The system SHALL require a last name or a company name, and SHALL flag an email address that is not syntactically valid, before allowing confirmation.

#### Scenario: Missing identity
- **WHEN** the user confirms with both last name and company empty
- **THEN** the system blocks submission and highlights the missing fields

#### Scenario: Invalid email
- **WHEN** the user confirms with an email value that is not a valid address
- **THEN** the system blocks submission and marks the email field as invalid

### Requirement: Company matching
The system SHALL search existing FundraisingBox companies by the card's company name, let the user link the contact to a match, and, when no match exists, propose creating the company in FundraisingBox and linking the contact to it, or proceeding without a company link.

#### Scenario: Existing company found
- **WHEN** the extracted company name matches one or more existing FundraisingBox companies
- **THEN** the user is offered the matches and can select one to link the contact to it

#### Scenario: No match
- **WHEN** no existing company matches
- **THEN** the user is offered to create the company and link the contact to it, or to proceed without a company link, and nothing is created until the user confirms

#### Scenario: Company-only card
- **WHEN** the card yields a company name but no person name
- **THEN** the user is offered to create only the company record (if no match exists) and no person is created

#### Scenario: Company search unavailable
- **WHEN** the FundraisingBox company search fails
- **THEN** the user sees a notice and can still proceed without a company link

### Requirement: Empty field highlighting
The system SHALL visually mark fields that were left empty by extraction so the reviewer can see what needs attention.

#### Scenario: Empty fields highlighted
- **WHEN** a field was not extracted
- **THEN** it is marked as empty in the review form by more than colour alone (for example a text hint or icon)
