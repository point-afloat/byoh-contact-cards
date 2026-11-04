# Proposal

## Why

A security review of the running app found one high-severity gap and several medium ones around the sign-in path. Anyone on the internet, without an account, can make the server accept and parse an arbitrarily large upload before it answers "401": there is no limit on request size anywhere. Sign-in throttling can also be used to lock a known user, such as the only administrator, out of their own account, or, behind Sliplane, to lock everybody out at once. This should be fixed before the app is reachable for longer than a short demo.

## What Changes

- Limit the size of every request body, and refuse oversized ones before they are read or parsed, with or without a login.
- Redo sign-in throttling so that one person's failed attempts no longer block another person's sign-in. Failures are counted per email and client address together, with a looser per-email limit as a backstop against guessing from many addresses.
- State and test how the client address is taken from the proxy, so a forged `X-Forwarded-For` header cannot be used to avoid throttling.
- Cap the length of the sign-in fields, and remove old failed-attempt rows and expired sessions, so neither can be used to grow the database.
- Name the sign-in cookie with the `__Host-` prefix when it is sent over HTTPS only.
- Send standard security headers on every response, and do not let the browser or a proxy cache API responses.
- Limit how many card uploads one signed-in user can start per hour, because each upload is a paid model call.
- Log a loud warning at startup when the sign-in cookie is not restricted to HTTPS.
- **BREAKING (one time):** renaming the cookie signs everybody out once when this is deployed.

Out of scope: a second factor (TOTP or passkeys), a breached-password check, an audit log of sign-ins and admin actions, and making the public health route less detailed. They are candidates for later changes.

## Capabilities

### New Capabilities

- `request-hardening`: limits and protections that apply to every request, whoever sends it: body size limits, security and cache headers, a per-user limit on card uploads, and the startup warning for an insecure cookie setting.
- `login-protection`: how sign-in is defended against guessing and abuse: throttling keys and limits, trusted client address, field length caps, clean-up of old records, and the cookie name.

### Modified Capabilities

None. The existing "Login throttling" and "Secure credential and cookie handling" requirements are in the `add-user-accounts` change, which has not been synced to `openspec/specs/` yet, so a delta cannot modify them. This change adds its own requirements instead. When `add-user-accounts` is synced, the older throttling requirement should be reconciled with `login-protection` (see design.md).

## Impact

- Code: a new request-size middleware and a new security-headers middleware, both wired into `app/main.py`; throttling, cookie and clean-up changes in `app/auth.py`, `app/auth_api.py` and `app/deps.py`; a per-user rate limit used by the upload route in `app/api.py`; new settings in `app/config.py`.
- Configuration: one new optional setting for the upload rate limit. Documented in the README table and `.env.example`.
- Deployment: `TRUSTED_PROXY` must be confirmed and set on Sliplane, and the Sliplane guide is updated. Everyone has to sign in again once after deployment.
- Frontend: no screens change. A 413 or 429 response shows the server's message through the existing error display.
- Database: no schema change. The existing `login_attempts` table already holds email and address.
- Dependencies: none.
