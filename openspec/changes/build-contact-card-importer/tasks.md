# Tasks

## 1. Project scaffolding and configuration

- [x] 1.1 Initialise the uv backend project (Python 3.12, FastAPI, httpx, pydantic, pydantic-settings, python-multipart, pillow; dev: pytest, respx, ruff, mypy) and verify `uv sync && uv run pytest` runs (even with zero tests)
- [x] 1.2 Add settings module reading `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT`, `FUNDRAISINGBOX_APITOKEN`, upload size limit; ship `.env.example`; verify a unit test shows missing required values raise a clear configuration error and secrets are not in `repr`/logs
- [x] 1.3 Create the FastAPI app skeleton with a `/api/health` route and uniform `{code, message}` error handler; verify with a TestClient test
- [x] 1.4 Scaffold `frontend/` with Vite + React + TypeScript, Tailwind CSS, shadcn/ui, ESLint, Vitest + Testing Library + MSW; configure the dev proxy for `/api`; verify `npm run dev`, `npm run build`, `npm run lint`, `npm test` all succeed on the starter page

## 2. Contact model and extraction (card-extraction)

- [x] 2.1 Define the pydantic `Contact` model (fields per card-extraction spec) and verify tests for defaults-empty and JSON-schema generation
- [x] 2.2 Implement upload validation (type, size) and image preparation (downscale, EXIF orientation fix); verify unit tests for each accepted/rejected case in the spec, including a PDF being rejected with the accepted-formats message
- [x] 2.3 Implement `ExtractionClient` against an OpenAI-compatible chat-completions endpoint with image input, tolerant JSON parsing and per-field validation; with temperature 0, a `max_tokens` cap, the image downscaled before sending, and at most one retry on malformed JSON; verify with `respx`-mocked tests for success, unreachable/timeout, malformed response (one retry, then partial result), and the request carrying the cap and temperature
- [ ] 2.4 Pick the model: run 10 real sample cards (printed and handwritten) through the cheapest candidate Mistral vision models, compare per-field accuracy and cost per card, choose the cheapest acceptable one, confirm that it accepts `json_schema` structured output with an image (and note what happens with `json_object`), record the result and default in `.env.example`/design.md, and verify switching `LLM_BASE_URL`/`LLM_MODEL` needs no code change (test with a second mocked base URL)
- [x] 2.5 Add in-memory TTL session store (image + contact + sent flag) with expiry and discard-on-send; verify tests for expiry and that card data never appears in log output
- [x] 2.6 Switch the extraction request to structured output: derive a strict schema from `Contact` (all fields required strings, `additionalProperties: false`), send it as `response_format` `json_schema`, fall back once to `json_object` when the endpoint rejects it (remember the choice), and add `LLM_RESPONSE_FORMAT` to settings and `.env.example`; update the extraction tests; verify `respx` tests for the schema in the request, fallback after a 400 unsupported-format reply (second request uses `json_object`), the forced `json_object` override, and that non-conforming output is still handled

## 3. FundraisingBox client (fundraisingbox-export)

- [x] 3.1 Verify against FundraisingBox API docs/sandbox which person fields accept email, phone, address, website; record the result in design.md Open Questions
- [x] 3.2 Implement `Contact → person payload` mapping including the ContactPilot custom field exactly as in the prototype (`{id: "16786", name: "ContactPilot", value: "Sync"}`, on persons), company_id handling, and channel data (phone, mobile, email, address, website) as labelled `info` lines, blocking when over 1000 characters; verify mapping unit tests (custom field present with the exact id, name and value, company linked, no company, email+phone in info, over-length blocked, salutation values match the API enum)
- [x] 3.3 Implement FundraisingBox client (`create_person`, `create_company`, `search_companies`) with typed errors; verify `respx` tests for success, 4xx/5xx with message, network failure, missing token (no request made)
- [ ] 3.4 Try company-record creation on a FundraisingBox test account (what `last_name`/`company_name`/`is_company` combination it accepts), record the result in design.md and adjust the company payload and its test; verify a company created this way appears in the company search

## 4. JSON API (card-extraction, contact-review, fundraisingbox-export)

- [x] 4.1 Implement `POST /api/sessions` (upload → extract → session id, contact, warnings), `GET /api/sessions/{id}`, `GET /api/sessions/{id}/image`, `PUT /api/sessions/{id}`; verify TestClient tests for accepted/rejected uploads, extraction failure leaving an empty editable contact, expired session
- [x] 4.2 Implement validation (last name or company required, valid email) reported on save (non-blocking, so drafts survive a reload) and enforced on send (wired in 4.3), and `GET /api/companies?q=` with graceful error; verify tests for both validation failures, match, no match, search error
- [x] 4.3 Implement `POST /api/sessions/{id}/send` with per-session lock and sent flag; verify tests for success, double submit creating one person, resend after success, API error then successful retry keeping data, missing token making no request
- [x] 4.4 Export the OpenAPI schema and generate TypeScript types into `frontend/src/api/`; add a drift-check script (`npm run api:check`, exit 1 on drift; wire it into CI once a CI system exists, none does yet); verify `npm run typecheck` passes against the generated types

## 5. Frontend (scan-ui, contact-review)

- [x] 5.1 Build the app shell: design tokens, light/dark theme from OS preference, step indicator, centralised UI strings, typed API client with TanStack Query; verify component tests for step rendering and theme switching
- [x] 5.2 Build the Upload screen (camera/file input, drag-and-drop, progress state, upload errors, accepted-format hint); verify Testing Library tests for accepted file, rejected type/size, in-progress disabled state (the real-phone check moved to 6.3)
- [x] 5.3 Build the Review screen (image beside/above form, field-config-driven react-hook-form + zod validation, empty-field hints not by colour alone, focus on first invalid field, session restore from URL on reload); verify tests for validation, empty-field hint, and reload restore
- [x] 5.4 Build the company picker (debounced search, select/none, graceful search failure); verify tests with MSW for match, no match, and failure
- [x] 5.5 Build send and Done flow (loading state, error message with preserved form and retry, disabled after success, "Scan next card"); verify tests for success, API error then retry, double click sending once
- [ ] 5.6 Accessibility and responsiveness pass: keyboard-only walkthrough, labels, announced errors, contrast in both themes, 360 px and 1280 px layouts; verify automated axe checks pass in tests and Lighthouse accessibility score ≥ 95 at phone width

## 6. Serving, documentation and integration check

- [ ] 6.1 Serve `frontend/dist` from FastAPI with SPA fallback, and add a multi-stage Dockerfile building frontend then backend; verify `docker build` and that the container serves the app and `/api/health`
- [ ] 6.2 Write README (backend and frontend setup, Node prerequisite, `npm run dev`/`build`, env vars, switching model endpoint, privacy note for hosted Mistral, single-worker/no-auth deployment note) and verify a fresh clone follows it to a running app
- [ ] 6.3 Run end-to-end on 5–10 real sample cards from a phone (including the camera capture on iOS Safari and Android Chrome, and whether iPhone photos arrive as HEIC) against a FundraisingBox test account (or dry-run mode if no sandbox exists) and verify created persons contain expected data; run `ruff`, `mypy`, `pytest`, `eslint`, `tsc`, `vitest` clean
