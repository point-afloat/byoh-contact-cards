# Spec Delta

## Purpose

Converts an uploaded contact card image into a structured contact record using a vision-capable language model whose endpoint can be replaced through configuration alone.

## ADDED Requirements

### Requirement: Accept card uploads
The system SHALL accept a contact card as a JPEG or PNG image upload, including a photo taken with a phone camera, and reject other types (including PDF) and files above a configured size limit.

#### Scenario: Image upload accepted
- **WHEN** the user uploads a JPEG or PNG card image within the size limit
- **THEN** the system starts extraction for that card

#### Scenario: Unsupported file rejected
- **WHEN** the user uploads a file that is not a JPEG or PNG image, such as a PDF
- **THEN** the system rejects it with a message naming the accepted formats and performs no extraction

#### Scenario: Oversized file rejected
- **WHEN** the uploaded file exceeds the configured size limit
- **THEN** the system rejects it with a message stating the limit

### Requirement: Structured contact output
The system SHALL return extracted data in a fixed schema with fields for salutation, title, first name, last name, company, position, email, phone, mobile, street, postal code, city, country, website, and notes, where any field not found on the card is empty rather than guessed.

#### Scenario: Printed card
- **WHEN** a card containing name, company, email, and phone is processed
- **THEN** the result contains those values in the matching fields and leaves absent fields empty

#### Scenario: Unreadable field
- **WHEN** the model cannot read a value on the card
- **THEN** that field is returned empty and the card is still returned for review

### Requirement: Schema-constrained model output
The system SHALL ask the model to answer in the contact schema using the endpoint's structured-output feature, so that the answer is machine-readable JSON with exactly the contact fields, and SHALL still validate every response before using it.

#### Scenario: Structured output requested
- **WHEN** the system sends a card to a model endpoint that supports structured output
- **THEN** the request asks for a response conforming to the contact schema with all contact fields as text values

#### Scenario: Endpoint without structured-output support
- **WHEN** the endpoint rejects the structured-output request because it does not support it
- **THEN** the system retries once in plain JSON mode and continues, without failing the card

#### Scenario: Conforming response
- **WHEN** the model returns a response that conforms to the schema
- **THEN** its values are used as the extracted contact, with empty text for fields not found on the card

#### Scenario: Non-conforming response still handled
- **WHEN** a response does not conform to the schema despite the request
- **THEN** it is handled as a malformed model response, keeping valid fields and noting that the result may be incomplete

### Requirement: Replaceable model endpoint
The system SHALL call an OpenAI-compatible chat-completions vision endpoint whose base URL, model name, and API key are set by configuration, with no code change required to switch provider.

#### Scenario: Default Mistral configuration
- **WHEN** the app is configured with the Mistral base URL, a vision-capable Mistral model, and an API key
- **THEN** extraction requests are sent to that endpoint and model

#### Scenario: Provider switched by configuration
- **WHEN** the base URL and model name are changed to another OpenAI-compatible endpoint and the app is restarted
- **THEN** extraction uses the new endpoint without any code change

#### Scenario: Missing configuration
- **WHEN** the endpoint URL, model name, or required API key is not configured
- **THEN** the app reports a clear configuration error at startup or on first use rather than failing obscurely

### Requirement: Extraction failure handling
The system SHALL report model endpoint failures, timeouts, and unparseable model responses to the user without crashing, and SHALL let the user retry or enter the contact manually.

#### Scenario: Endpoint unreachable
- **WHEN** the model endpoint cannot be reached or times out
- **THEN** the user sees an error explaining that extraction failed and can retry or continue with an empty form

#### Scenario: Malformed model response
- **WHEN** the model returns output that does not conform to the contact schema
- **THEN** the system discards the invalid parts, keeps any valid fields, and shows a notice that the result may be incomplete

### Requirement: No persistent storage of card data
The system SHALL NOT persist uploaded card images or extracted contacts beyond the lifetime of the review session, and SHALL NOT write their contents to logs.

#### Scenario: Session ends
- **WHEN** a contact has been sent or the review session is abandoned
- **THEN** the uploaded image and extracted data are discarded from the server
