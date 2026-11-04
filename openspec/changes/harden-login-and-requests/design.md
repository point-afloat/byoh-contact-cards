# Design

## Context

See proposal.md for why. The app is one FastAPI process with a single worker, SQLite under `DATA_DIR`, in-memory review sessions, and an `@app.middleware("http")` CSRF guard in `app/main.py`. Settings are loaded lazily (`ensure_services`), so importing the app never needs configuration.

Facts that shape the approach:

- FastAPI parses a request body (including multipart) **before** it runs the dependency that checks the login. A route-level check therefore cannot stop an anonymous upload from being parsed. This was confirmed with a probe: a 5 MB anonymous multipart request with an `X-Requested-With` header was parsed, then answered with 401.
- The `login_attempts` table already stores email and address for every failure, so re-keying the throttle needs no schema change.
- The throttle and the client address are only as good as the proxy header. Sliplane's behaviour is not documented and has to be checked on the real server.
- The scenarios in `specs/` replace nothing yet: the older "Login throttling" requirement sits in the unsynced `add-user-accounts` change.

## Goals / Non-Goals

**Goals:**
- No request body is read or parsed beyond its limit, for anyone.
- Throttling stops guessing without letting a stranger lock out a real user.
- Every limit and header has a test that fails when it is removed.

**Non-Goals:**
- A second factor, a breached-password check, an audit log, and trimming the public health route.
- Rate limiting by address across the whole API. Only sign-in and card uploads are limited.
- A shared rate-limit store. Limits live in one process, which matches the single-worker design.

## Decisions

1. **A pure ASGI middleware for the size limit, outermost.** It checks `Content-Length` first and also counts bytes as they arrive, for clients that stream without a length. Alternatives: the existing `@app.middleware("http")` style (it buffers through `BaseHTTPMiddleware` and cannot cut a streamed body off cleanly); a limit set in uvicorn (it has no body limit option); relying on Sliplane's proxy (undocumented). Being outermost means it runs before the CSRF guard and before FastAPI reads anything.

2. **Limits: 64 KB for JSON, upload limit plus 64 KB for `/api/sessions`.** The only large body in the app is the card image. The allowance covers multipart boundaries and headers. The upload limit is read lazily per request, and falls back to the 10 MiB default if settings are invalid, so a configuration error still gets its normal clear 503 instead of a crash in the middleware.

2a. **Cookie-less card uploads are refused unread, in the same middleware, after the size check.** The size limit alone still lets an anonymous caller make the server parse a body of up to the upload limit before the 401. The middleware checks only that a session cookie is present, not that it is valid. Alternatives: look the cookie up in the database in the middleware (a database read for every anonymous request, and a second copy of the sign-in rules); a route dependency (it runs after FastAPI has parsed the body, which is the original problem). The residual risk is a request that carries a made-up cookie: it is still parsed, bounded by the size limit. That is accepted, and the limit's size is what bounds it. The 401 body must match the one the usual check returns, and a test compares the two. The cookie name is passed in as a value that is looked up per request, so the `__Host-` rename in group 2 only changes one line.

3. **Throttle keyed three ways, using the existing table.** Strict: 5 per email and address. Backstop: 30 per email across addresses. Address limit: 20 per address (as today). Alternatives: keep per-email only (anyone can lock out the admin with five requests); progressive delays instead of blocks (needs per-attempt state and holds a connection or a thread); a CAPTCHA (third-party service, bad on a phone). The backstop keeps distributed guessing bounded, at about 4,300 guesses per email per day, against passwords of at least 12 characters. The residual risk is that an attacker who makes 30 failed attempts can still block that email for 10 minutes. That is accepted and written down, because the alternative is no cap on distributed guessing.

4. **Success clears only the pair.** Today a success deletes every failure for the email, which also wipes out an attacker's counter. Clearing the pair only keeps the counts from other addresses.

5. **Oversized login fields are rejected by the request model, with a 422 and no recorded failure.** A failure row with an enormous email is the way to grow the table; refusing it up front costs nothing. Limits match what the rest of the app allows (320 for an email, 1024 for a password).

6. **Purge during sign-in, at most once a minute.** Delete failed attempts older than the window and expired sessions in the sign-in path, guarded by a timestamp kept in memory. Alternatives: a background thread or scheduled job (more moving parts, and the single-process app has no scheduler); purging on every request (a write on every call). Sign-in is the only path that adds failure rows, so it is also the right place to clean them up.

7. **`__Host-session` only when the cookie is secure.** The prefix requires the `Secure` attribute, path `/` and no domain, and browsers reject it over plain http, which would break local development. So the name depends on `AUTH_COOKIE_SECURE`. The old `session` cookie is no longer read, and is deleted after the next successful sign-in. The cost is one forced sign-in for everyone when this is deployed.

8. **Security headers from a second pure ASGI middleware.** The policy is `default-src 'self'; img-src 'self' blob: data:; style-src 'self'; style-src-attr 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'`. `blob:` is for the image preview. `style-src-attr 'unsafe-inline'` is only a fallback in case the UI sets inline styles, and is dropped if the real-browser check shows none are needed. HSTS is sent only when the cookie is secure, for 180 days, without `includeSubDomains` or `preload`, so a wrong guess about the host is not permanent. `Cache-Control: no-store` is added on `/api` responses, because they carry names and card data.

9. **The policy is verified in a real browser, not only in unit tests.** A unit test can show that the header is present but not that the app still works under it. The project already used headless Chrome for the 360 px layout check, so a repeatable script is added.

10. **Upload rate limit: a sliding window per user in memory.** 120 uploads per hour by default, configurable. An upload counts once it has passed validation and is about to go to the model, so a refused file costs nothing. Alternatives: a database counter (a write per upload and a table to clean up for no benefit in a single process); a limit per address (does not stop one account). It resets on restart, which is acceptable for a cost guard.

11. **The insecure-cookie warning goes to the log, not the health route.** The health route is public. Reporting the setting there would tell any visitor how the deployment is configured. A startup log line reaches the person who deploys it.

12. **Overlap with `add-user-accounts`.** That change's "Login throttling" requirement says "more than 5 failures per email in 10 minutes". When it is synced, the new `login-protection` requirement supersedes it. Before syncing, edit or remove the older requirement so two specs do not describe different limits.

## Risks / Trade-offs

- [The content security policy blocks something the app needs, and the app breaks in the browser] → decision 9, plus a check of every screen in headless Chrome for violations before the group is ticked.
- [`TRUSTED_PROXY` is set where Sliplane adds more than one hop, so the "last entry" is an internal address and everyone shares one throttle bucket] → a check on the deployed server before enabling it (the follow-up at the end of tasks.md and step 9 of docs/demo-day-plan.md): failures with a forged header must still be throttled, and two different networks must be counted separately. It cannot be run before the first deployment, so it is not a tracked task.
- [Until that check passes, `TRUSTED_PROXY` stays off and every visitor behind Sliplane shares one address] → the pair limit then behaves like a per-email limit and the address limit can block everyone after 20 failures. The code and tests are correct, but the lockout redesign only helps in production once the check is done.
- [An attacker can block one known email for 10 minutes with 30 requests] → accepted (decision 3). The administrator can always reset a user's password, and `INITIAL_ADMIN_*` recovery stays as the documented break-glass.
- [Renaming the cookie signs everyone out once] → announced in the deployment guide. No data is lost, since review sessions are short-lived anyway.
- [HSTS locks a host to HTTPS for 180 days] → no `includeSubDomains` or `preload`, and it is sent only when the secure cookie is on.
- [The in-memory upload limit resets when the container restarts] → accepted for a cost guard.

## Migration Plan

1. Deploy as normal. No database migration.
2. Everyone signs in once more.
3. Set `TRUSTED_PROXY=true` only after the check in the follow-up (step 9 of docs/demo-day-plan.md) passes.
4. Roll back by redeploying the previous image. The old cookie name works again, which signs people out once more.
