# sign-in-password-visibility Specification

## Purpose
Defines how a person can check the password they type on the sign-in form by revealing and hiding it.

## Requirements

### Requirement: Password can be revealed and hidden
The sign-in form SHALL offer a button next to the password field that switches the field between hidden and visible text, keeping the entered value, and the field SHALL start hidden.

#### Scenario: Reveal the typed password
- **WHEN** a person has typed a password and activates the show control
- **THEN** the field shows the text they typed and the control now offers to hide it

#### Scenario: Hide it again
- **WHEN** the password is visible and the person activates the hide control
- **THEN** the field is hidden again and still holds the same value

#### Scenario: Hidden by default
- **WHEN** the sign-in form is opened
- **THEN** the password field is empty and its text is hidden

#### Scenario: A failed attempt keeps the choice
- **WHEN** a sign-in attempt fails while the password is visible
- **THEN** the field is emptied and stays in the mode the person chose

### Requirement: The control is accessible
The show/hide control SHALL be reachable and operable with the keyboard, have an accessible name that says what it will do, and expose whether the password is currently shown.

#### Scenario: Keyboard and screen reader
- **WHEN** a person tabs to the control and activates it with the keyboard
- **THEN** the password toggles, and a screen reader announces the name "Show password" or "Hide password" and the pressed state
