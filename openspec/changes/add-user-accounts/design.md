# Design

## Context

Builds on `build-contact-card-importer` (FastAPI JSON API under `/api`, React SPA, in-memory review sessions, single worker) and `add-sliplane-docker-deployment` (container on Sliplane, public URL). Proxy-based auth was considered and dropped because users would live in config and need a developer to change; see proposal.md. This is the first persistent data in the app, so it also needs a volume.

## Goals / Non-Goals

**Goals:**
- Self-service user lifecycle for NGO admins, with no developer involvement after the first deploy.
- Small, conventional, auditable auth implementation.
- Auth wraps every existing route without each route handling it.

**Non-Goals:**
- SSO/OAuth, 2FA, email sending, self-service forgot-password, audit log UI, multi-tenant or per-user card history.

## Decisions

1. **Storage: SQLite file on a mounted volume** (`DATA_DIR`, default `/data`), accessed with SQLAlchemy 2 and Alembic migrations run at startup. Tables: `users`, `invites` (invite and reset tokens), `sessions`, `login_attempts`. Fits the single-worker design; no extra service to run. *Alternatives:* Postgres (extra Sliplane service for ~10 users), JSON file (no integrity or concurrency safety). Card data is never written to it.

2. **Passwords: argon2id** via `argon2-cffi` with library defaults, minimum 12 characters, no composition rules, and a small common-password check. *Alternative:* bcrypt (acceptable, but argon2id is the current default recommendation).

3. **Sessions: server-side**, random 256-bit id stored hashed in `sessions`, delivered in an HTTP-only, `Secure`, `SameSite=Lax` cookie with idle and absolute lifetimes. Server-side storage makes deactivation and password changes revoke sessions immediately, which stateless JWTs cannot do. *Alternative:* signed JWT cookies (simpler, but not revocable).

4. **CSRF:** `SameSite=Lax` plus requiring `Content-Type: application/json` or a custom `X-Requested-With` header on state-changing API calls; the SPA is same-origin, so no CORS is enabled.

5. **Tokens for invites and resets:** random 256-bit value, only its hash stored, single use, expiry configurable (default 7 days for invites, 1 hour for resets). Links are `/accept-invite#token=...` using the URL fragment so tokens are not sent in server logs or Referer headers. Re-issuing invalidates earlier tokens.

6. **Auth as a FastAPI dependency** (`current_user`, `require_admin`) applied at router level to everything under `/api` except an explicit allow-list (`/api/health`, login, accept-invite). A test calls every operation in the app's OpenAPI schema anonymously and fails unless it answers 401 or is on the explicit public list (`/api/health`, login, invite-info, accept-invite), so future routes can't be left open by accident. (Behavioural rather than inspecting FastAPI's route objects, which changed shape in FastAPI 0.162.) State-changing requests also need a JSON body or an `X-Requested-With` header (CSRF guard).

7. **Login throttling:** counts failures per normalized email and per client IP in `login_attempts` (5 per 10 minutes, then cooling-off); constant-time verification and generic errors to avoid user enumeration. The client IP is read from the proxy header only when `TRUSTED_PROXY` is enabled, since Sliplane sits in front.

8. **Bootstrap admin:** if `users` is empty at startup, create an admin from `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD`; otherwise ignore them. Startup fails fast (and health reports 503) if both are missing on an empty database. The runbook tells the operator to remove `INITIAL_ADMIN_PASSWORD` afterwards.

9. **Frontend:** routes `/login`, `/accept-invite`, `/account` (change password, sign out), and `/admin/users` (visible only to admins), with a small path router instead of a routing library. A `useAuth` provider based on `GET /api/auth/me` sends people who are not signed in to the sign-in page. When the server ends a session mid-use, the page stays mounted and a sign-in dialog opens over it, so unsent form values survive. User table uses shadcn/ui components; invite and reset links are shown in a dialog with a copy button and expiry. Reuses the design system and accessibility rules from `scan-ui`.

10. **API:** `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/change-password`, `POST /api/auth/invite-info` (lets the page tell a valid link from a used or expired one without using it up), `POST /api/auth/accept-invite` (also used for reset links), and under `/api/admin/users`: `GET`, `POST` (invite), `PATCH /{id}` (role, active), `POST /{id}/invite` (new link), `POST /{id}/reset-link`, `DELETE /{id}/invite` (revoke). TypeScript types continue to be generated from OpenAPI.

11. **Tests:** pytest for hashing, token lifecycle, session revocation, throttling, last-admin guard, route-protection enumeration; Vitest/Testing Library and axe for the screens.

## Risks / Trade-offs

- [Hand-rolled auth has bugs] → use proven libraries (argon2-cffi, standard cookie flags), keep the surface small, enumerate-routes test, and review before first production use.
- [SQLite file lost if the volume is lost] → users can be rebuilt by the bootstrap admin; document a periodic volume backup option from Sliplane; no card data at risk.
- [Invite links shared over insecure channels] → single use, short expiry, shown only to the admin; admins can revoke.
- [No email means admins must pass links manually] → acceptable for 10 users; SMTP can be added without changing specs.
- [No self-service password reset] → admin issues a reset link; documented in the runbook and Users screen.
- [Lockout of all admins] → last-admin guard, and the bootstrap env vars can be re-enabled by clearing the database volume as documented break-glass.
- [Throttling by IP behind a proxy] → only trust forwarded headers when explicitly configured.

## Migration Plan

Alembic creates the schema on first start. The first deploy sets `INITIAL_ADMIN_*`; afterwards the password variable is removed. Rollback to a version without auth is not supported once the volume holds users.

## Open Questions

- Display name field for users (optional, nice for the Users screen); can be added without changing the core specs.
