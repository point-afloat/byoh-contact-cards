# Proposal

## Why

The contact card importer will be hosted on a public URL and used by about 10 NGO staff. It handles personal data and can create records in FundraisingBox, so only known people may use it. Proxy-level basic auth (shared or per-user) keeps users in config files and needs a developer for every new colleague. The NGO must be able to add and remove users themselves, from within the app, without involving the developer.

## What Changes

- Login with email and password; all app pages and API routes except the login/invite pages and health check require a signed-in user.
- Two roles: **admin** (manages users) and **member** (scans and sends cards).
- Admins invite users by email address from a Users screen; the app creates a single-use, expiring invite link the admin can copy and share, and the invitee sets their own password. Admins can also deactivate/reactivate users, change roles, and issue password-reset links.
- Signed-in users can change their own password and sign out.
- The first admin is created from deployment environment variables when no users exist yet.
- Protections: strong password hashing, revocable server-side sessions (deactivating a user signs them out), login rate limiting, and a guard against removing the last admin.
- Small persistent database (users, invites, sessions only) stored on a mounted volume. Card images and contact data remain in memory only.

## Capabilities

### New Capabilities
- `user-authentication`: signing in and out, session handling, protected access to the app and API, password change, login throttling, and bootstrap of the first admin.
- `user-administration`: admin-managed user lifecycle: invitations, roles, deactivation, password reset links, and last-admin protection.

### Modified Capabilities
<!-- None in openspec/specs (empty). The related change add-sliplane-docker-deployment drops its proxy-based access-control capability in favour of this one. -->

## Impact

- Backend: user/invite/session storage (SQLite), auth endpoints, auth dependency on all existing API routes, admin endpoints. Builds on `build-contact-card-importer` (must be implemented first).
- Frontend: login, invite-acceptance, change-password and admin Users screens plus an authenticated app shell with sign-out; same design system and accessibility rules as `scan-ui`.
- Deployment: requires a persistent volume mounted for the database (see `add-sliplane-docker-deployment`); new env vars for the initial admin and session secret.
- Security/privacy: the app becomes the access boundary, so correctness of auth matters; user emails become stored personal data (minimal: email, name optional, role, timestamps).
- Reverses the earlier assumption "no authentication / no persistence" for users only; the no-persistence rule for card data in `card-extraction` is unchanged.

## Assumptions

- Invite links are copied by the admin and shared themselves (chat/email). Sending invitation emails from the app is out of scope; adding SMTP later would not change the specs.
- Email addresses are the usernames; no username field.
- Password reset is admin-initiated; self-service "forgot password" is out of scope because it needs outgoing email.
- Single container/worker, so SQLite on a volume is sufficient.
- Out of scope: SSO/OAuth, two-factor authentication, audit log UI, per-user cards or history, API tokens.
