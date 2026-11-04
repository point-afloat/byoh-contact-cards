# Tasks

## 1. Request size limits

- [x] 1.1 Write the pure ASGI size-limit middleware (declared length, byte counting for streamed bodies, 400 for a bad length, 413 with the usual error body). Verify with tests for each scenario in `request-hardening`: declared too large, streamed too large, 64 KB JSON, upload exactly at the limit, malformed length. (files: app/body_limit.py, tests/test_body_limit.py)
- [x] 1.2 Wire it outermost in `create_app`, reading the upload limit lazily with the 10 MiB fallback. Verify that an anonymous multipart request larger than the configured upload limit (sent with `X-Requested-With`) gets 413 and the multipart parser is never called, and that the existing upload tests still pass. Also make the test suite ignore a developer's `.env` file (done before 1.2 because it hid real results): `tests/conftest.py` switches the file off for every test, and the whole suite passes from the project root with a `.env` present. (files: app/main.py, tests/test_body_limit.py, tests/conftest.py, tests/test_config.py)
- [x] 1.3 Refuse card uploads that carry no session cookie before reading their body, after the size check and with the same 401 body as the usual sign-in check. Verify with tests that a cookie-less upload within the limit gets 401 with the multipart parser never called, that an oversized one still gets 413, that a made-up cookie is checked in the usual way, that other routes and methods are not affected, and that the early 401 body equals the usual one. (files: app/body_limit.py, app/main.py, tests/test_body_limit.py, tests/test_api_sessions.py)
- [x] 1.4 Checkpoint: owner reviews and commits this group (tasks 1.1 to 1.3)

## 2. Sign-in protection

- [x] 2.1 Re-key the throttle: 5 per email and address, 30 per email, 20 per address; a success clears only that pair; refused attempts are not counted. Verify with tests for every scenario in "Throttling keyed by email and client address", including the stranger-cannot-block case and unknown emails behaving like known ones. (files: app/auth.py, tests/test_auth.py, tests/test_auth_api.py)
- [x] 2.2 Cap the sign-in fields at 320 and 1024 characters in the request model, with no failure recorded and no hash computed. Verify with tests that an oversized email and an oversized password get a 422 and leave `login_attempts` unchanged. (files: app/auth_api.py, tests/test_auth_api.py)
- [x] 2.3 Purge failed attempts older than the window and expired sessions during sign-in, at most once a minute. Verify with a test that uses the injected clock to age rows, and a test that the purge does not run twice within a minute. (files: app/auth.py, tests/test_auth.py)
- [x] 2.4 Use the `__Host-session` cookie name when the cookie is secure and `session` otherwise; stop reading the old name; delete the old cookie after a sign-in. Verify with tests for the secure name and attributes, the plain name for local development, and a request carrying only the old cookie being treated as signed out. Update the existing tests that use the old name. (files: app/auth.py, app/auth_api.py, app/deps.py, tests/test_auth_api.py, tests/auth_helpers.py)
- [x] 2.5 Pin down the client address rules. Verify with tests that, with the proxy trusted, a forged leading `X-Forwarded-For` entry does not change the counted address, that an empty header falls back to the connection address, and that the header is ignored when the proxy setting is off. (files: app/deps.py, tests/test_deps.py)
- [ ] 2.6 Checkpoint: owner reviews and commits this group (tasks 2.1 to 2.5)

## 3. Response hardening and upload cost limits

- [x] 3.1 Write the security-headers middleware: content security policy, `nosniff`, `no-referrer`, `X-Frame-Options`, HSTS only when the cookie is secure, `no-store` on `/api`. Wire it into `create_app`. Verify with tests that each header appears on the start page and on an API response, and that HSTS follows the cookie setting. (files: app/security_headers.py, app/main.py, tests/test_security_headers.py)
- [ ] 3.2 Add a repeatable check that opens the built app in headless Chrome, signs in, uploads a card against a stubbed model and a mocked FundraisingBox, and fails on any content security policy violation. Verify it passes against the container image, and fails when the policy is made stricter on purpose (for example by dropping `blob:`). (files: scripts/check-headers.sh)
- [ ] 3.3 Add the per-user upload rate limit (default 120 per hour) as a new setting, count an upload only after it passes validation, and return 429 with a "try again later" message. Document the setting in the README table and `.env.example`. Verify with tests for over the limit, another user unaffected, the window passing and refused files not counting, and that `tests/test_env_docs.py` passes. (files: app/rate_limit.py, app/api.py, app/config.py, README.md, .env.example, tests/test_rate_limit.py, tests/test_env_docs.py)
- [ ] 3.4 Log a startup warning when `AUTH_COOKIE_SECURE` is false and never include it in the health response. Verify with tests that the warning is logged for false, not logged for true, and that `/api/health` does not mention it. (files: app/health.py, tests/test_health.py)
- [ ] 3.5 Checkpoint: owner reviews and commits this group (tasks 3.1 to 3.4)

## 4. Deployment and final checks

- [ ] 4.1 Update the Sliplane guide for the one-time sign-out, the `TRUSTED_PROXY` check and the new setting, and add a short note on lockouts to the admin guide. Verify that `frontend/src/docs.test.ts` and `tests/test_env_docs.py` pass and that every new variable appears in the README table. (files: docs/deployment-sliplane.md, docs/admin-guide.md, README.md)
- [ ] 4.2 Run the whole suite and the container checks: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy app`, `npm test` and `npm run api:check` in `frontend/`, and `scripts/smoke-container.sh`. Verify all pass and the smoke script covers the 413 and the security headers. (files: scripts/smoke-container.sh)
- [ ] 4.3 Checkpoint: owner reviews and commits this group (tasks 4.1 to 4.2)

## Workflow follow-up

These need the deployed Sliplane server, which is not available yet. They are reference steps, not tracked tasks, so they do not hold up archiving this change.

- On the deployed server, confirm the client address handling before turning `TRUSTED_PROXY` on: with `TRUSTED_PROXY=true`, five failed sign-ins for a made-up email with different forged `X-Forwarded-For` values must still be throttled, and a sign-in for the same email from a second network must not be blocked by the first. The steps are in `docs/demo-day-plan.md` (step 9 of "On the day"). Until it passes, leave `TRUSTED_PROXY` off.
- Until then the lockout redesign has no effect behind the proxy: every visitor shares one address.
