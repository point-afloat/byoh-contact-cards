# Spec Delta

## Purpose

Defines the look, responsiveness, and accessibility of the scan, review, and completion experience so the app is pleasant and dependable on phones and desktops.

## ADDED Requirements

### Requirement: Guided step flow
The system SHALL guide the user through three steps (upload, review, done), show which step is active, and offer "scan next card" after a successful send.

#### Scenario: Normal flow
- **WHEN** the user uploads a card, reviews it, and sends it
- **THEN** the interface moves through upload, review, and done in order and the done step offers to start over

#### Scenario: Reload during review
- **WHEN** the user reloads the page while reviewing an unexpired session
- **THEN** the review step is restored with the card image and current values

### Requirement: Mobile-first responsive layout
The system SHALL be fully usable from a 360 px wide viewport up to desktop widths without horizontal scrolling, stacking the image above the form on narrow screens and placing them side by side on wide screens.

#### Scenario: Phone width
- **WHEN** the viewport is 360 px wide
- **THEN** all controls are reachable without horizontal scrolling and touch targets are at least 44 px high

#### Scenario: Desktop width
- **WHEN** the viewport is 1280 px wide
- **THEN** the card image and the review form are displayed side by side

### Requirement: Camera and file capture
The system SHALL let the user take a photo with the device camera where available or pick a file, and on desktop SHALL also accept drag-and-drop.

#### Scenario: Phone camera
- **WHEN** the user taps the capture control on a phone
- **THEN** the device camera or photo picker opens and the chosen image is uploaded

### Requirement: Progress and status feedback
The system SHALL show a visible loading state while extraction or sending is in progress, disable the triggering control meanwhile, and present success and error outcomes as clearly worded messages.

#### Scenario: Extraction in progress
- **WHEN** extraction takes several seconds
- **THEN** the user sees a progress indicator and cannot start a second upload for the same card

#### Scenario: Error shown
- **WHEN** an operation fails
- **THEN** a message states what failed and the available next action

### Requirement: Accessibility
The system SHALL be operable by keyboard alone, label every form field, show a visible focus indicator, announce validation and status messages to assistive technology, and meet WCAG 2.1 AA colour contrast.

#### Scenario: Keyboard-only review
- **WHEN** a user navigates the review form with the keyboard only
- **THEN** every field and action is reachable in a logical order and focus is always visible

#### Scenario: Validation announced
- **WHEN** validation blocks submission
- **THEN** the first invalid field receives focus and the error text is exposed to screen readers

### Requirement: Consistent visual design and themes
The system SHALL use one consistent design system for typography, spacing, colours, and components, and SHALL follow the operating system's light or dark preference.

#### Scenario: Dark mode
- **WHEN** the operating system prefers a dark theme
- **THEN** the app renders in a dark theme that still meets contrast requirements
