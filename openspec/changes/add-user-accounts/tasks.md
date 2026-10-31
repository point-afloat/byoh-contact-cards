# Tasks

## 1. Storage and security primitives

- [ ] 1.1 Add SQLAlchemy 2, Alembic and argon2-cffi; create `users`, `invites`, `sessions`, `login_attempts` models and the initial migration run at startup against `DATA_DIR`; verify a test that a fresh directory migrates and a restart keeps data
- [ ] 1.2 Implement password hashing/verification with the 12-character minimum and common-password check; verify unit tests for hash format (argon2id), rejection of short/common passwords, and that no plaintext appears in the database
- [ ] 1.3 Implement token generation and hashed storage for invites/resets (single use, expiry, re-issue invalidates old); verify unit tests for use, reuse, expiry and re-issue

## 2. Authentication API (user-authentication)

- [ ] 2.1 Implement server-side sessions with secure cookie flags, idle/absolute expiry and revocation, plus `login`, `logout`, `me`; verify tests for valid/invalid credentials with identical generic errors, deactivated user, cookie flags, and expiry
- [ ] 2.2 Implement `change-password` (current password required, other sessions revoked) ; verify tests for success, wrong current password, and revocation of other sessions
- [ ] 2.3 Implement login throttling (per email and per client IP, cooling-off, trusted-proxy aware); verify a test for 6 failures within 10 minutes blocking a correct password
- [ ] 2.4 Apply `current_user` at router level with an explicit allow-list (`/api/health`, login, accept-invite) and the CSRF header/content-type check; verify an enumerating test that fails if any non-allow-listed route lacks auth, and 401 with no side effects for anonymous calls to existing extraction/send routes
- [ ] 2.5 Implement bootstrap of the first admin from `INITIAL_ADMIN_EMAIL`/`INITIAL_ADMIN_PASSWORD` including fail-fast and health 503 when unconfigured; verify tests for empty DB, existing users (ignored), and nothing configured
- [ ] 2.6 Verify logs never contain passwords, tokens or session ids with a log-capture test across login, invite and reset flows

## 3. User administration API (user-administration)

- [ ] 3.1 Implement `require_admin` and admin endpoints to list users, invite (email + role, duplicate refused), re-issue and revoke invites; verify tests including member receiving 403
- [ ] 3.2 Implement `accept-invite` (set password, activate, sign in; used/expired links rejected); verify tests for valid, used and expired links
- [ ] 3.3 Implement deactivate/reactivate, role change, admin-issued reset link and last-admin protection; verify tests for session revocation on deactivation, reactivation with old password, reset flow, and refusing the last admin's self-deactivation/demotion
- [ ] 3.4 Regenerate OpenAPI TypeScript types and verify the drift check and `npm run typecheck` pass

## 4. Frontend (user-authentication, user-administration)

- [ ] 4.1 Add `useAuth` provider, route guards, 401 redirect to login, and account menu with sign-out; verify Testing Library tests for anonymous redirect and sign-out
- [ ] 4.2 Build Login and Account (change password) screens with validation, generic error text, throttling message and accessible focus/announcements; verify tests and axe checks
- [ ] 4.3 Build Accept-invite screen reading the token from the URL fragment (also used for reset links) with password rules and invalid-link state; verify tests for valid, expired and used links
- [ ] 4.4 Build admin Users screen: table, invite dialog with copy-link and expiry, deactivate (with confirmation)/reactivate, role change, reset link, revoke/re-issue invite, hidden for members; verify tests for each action and a 360 px layout check
- [ ] 4.5 Show a "session expired, please sign in" message on mid-use 401 without losing unsent form values where feasible; verify a test for this flow

## 5. Documentation and integration check

- [ ] 5.1 Document first-admin bootstrap, `DATA_DIR`/volume, env vars (`INITIAL_ADMIN_*`, session lifetimes, `TRUSTED_PROXY`), admin guide for the NGO (inviting, deactivating, resetting, break-glass), and password policy; verify a non-developer follows the admin guide to add a user
- [ ] 5.2 End-to-end check on the deployed instance: bootstrap admin signs in, invites a second user who accepts on a phone and sends a card, admin deactivates that user and their session ends; run `ruff`, `mypy`, `pytest`, `eslint`, `tsc`, `vitest` clean

## Workflow follow-up

- Apply after `build-contact-card-importer` and together with `add-sliplane-docker-deployment`, which provides the volume and no longer uses a proxy.
