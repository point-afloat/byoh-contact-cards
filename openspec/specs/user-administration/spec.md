# user-administration Specification

## Purpose
Lets NGO administrators manage who can use the app, including adding and removing colleagues, entirely within the app without developer involvement.

## Requirements

### Requirement: Admin-only user management
The system SHALL restrict the Users screen and all user-management actions to users with the admin role and SHALL refuse them for members with a 403 response.

#### Scenario: Member access
- **WHEN** a member opens the Users screen or calls a user-management endpoint
- **THEN** access is refused and no user data is returned

#### Scenario: Admin access
- **WHEN** an admin opens the Users screen
- **THEN** they see all users with email, role, status, and last sign-in

### Requirement: Invite a user
The system SHALL let an admin invite a person by email address and role, producing a single-use invite link that expires after a configured period and that the admin can copy.

#### Scenario: Create invite
- **WHEN** an admin enters a new email address and role
- **THEN** the system shows an invite link with its expiry date and lists the user as invited

#### Scenario: Duplicate email
- **WHEN** an admin invites an email address that already belongs to a user
- **THEN** the invite is refused with a message explaining that the user exists

### Requirement: Accept an invite
The system SHALL let the invitee open the link, choose a password that meets the password rules, and then be signed in; the link SHALL stop working after use or expiry.

#### Scenario: Valid invite
- **WHEN** the invitee opens an unused, unexpired link and sets a valid password
- **THEN** their account becomes active and they are signed in

#### Scenario: Used or expired invite
- **WHEN** a link is opened after it was used or after it expired
- **THEN** the system shows that the invite is no longer valid and suggests asking an admin for a new one

### Requirement: Resend or revoke an invite
The system SHALL let an admin issue a fresh invite link for a pending user, which invalidates earlier links, and revoke a pending invite.

#### Scenario: New link
- **WHEN** an admin generates a new link for a pending user
- **THEN** the old link no longer works and the new one does

### Requirement: Deactivate and reactivate users
The system SHALL let an admin deactivate a user, which blocks sign-in and ends their sessions, and reactivate them later without losing the account.

#### Scenario: Deactivate
- **WHEN** an admin deactivates a user
- **THEN** the user can no longer sign in and the Users screen shows them as inactive

#### Scenario: Reactivate
- **WHEN** an admin reactivates a user
- **THEN** the user can sign in again with their existing password

### Requirement: Change roles
The system SHALL let an admin change another user's role between admin and member.

#### Scenario: Promote member
- **WHEN** an admin changes a member to admin
- **THEN** that user gains access to the Users screen on their next request

### Requirement: Admin-issued password reset
The system SHALL let an admin issue a single-use, expiring password-reset link for any active user, which ends that user's sessions when used.

#### Scenario: Reset link used
- **WHEN** the user opens the reset link and sets a valid new password
- **THEN** the old password stops working and the user is signed in

### Requirement: Last admin protection
The system SHALL NOT allow the last active admin to be deactivated or demoted, including by themselves.

#### Scenario: Only admin tries to deactivate self
- **WHEN** the only active admin attempts to deactivate or demote themselves
- **THEN** the action is refused with an explanation

### Requirement: Usable user management screen
The system SHALL present user management with the same responsive and accessible behavior as the rest of the app, with confirmation before deactivating a user.

#### Scenario: Phone width
- **WHEN** an admin uses the Users screen on a 360 px wide viewport
- **THEN** all actions are reachable without horizontal scrolling

#### Scenario: Deactivation confirmation
- **WHEN** an admin chooses to deactivate a user
- **THEN** the system asks for confirmation naming the user before applying it
