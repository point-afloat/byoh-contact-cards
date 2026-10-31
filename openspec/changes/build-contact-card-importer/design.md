# Design

## Context

Greenfield repository. The prototype in `../contact_cards` (observed) uses Streamlit, FastAPI, local OCR/Qwen3-VL and a `httpx` call to `https://api.fundraisingbox.com/v1/persons.json` with basic auth `(token, "X")`. Observed FundraisingBox behavior from the prototype: the account models donors as companies, existing records have only `company_name`, and creating persons with identity fields against such companies triggers a `not_editable` error, so linking via `company_id` is preferred. `FundraisingBoxRequest` there supports salutation, title, names, position, info, company_id/name and a ContactPilot custom field (`{id: "16786", name: "ContactPilot", value: "Sync"}`, sent on every person; the value `Sync` is what the ContactPilot integration reacts to, so it must be kept exactly); it has no email/phone/address fields, which is unresolved (see Open Questions). See proposal.md for motivation and the specs for requirements.

## Goals / Non-Goals

**Goals:**
- Phone-friendly scan → review → send flow with minimal moving parts.
- One narrow `ExtractionClient` boundary so the model endpoint is swapped by env vars.
- Stateless server: no database, nothing persisted.

**Non-Goals:**
- Accounts/authentication, batch import, history, updating existing FundraisingBox persons, offline mode/PWA install, native mobile app, server-side rendering, i18n (UI language is a single fixed language, to be confirmed).
- Local OCR engines (Tesseract/EasyOCR) from the prototype.

## Decisions

1. **Backend: Python 3.12 + FastAPI as a JSON API, uv-managed.** Python is retained so prototype knowledge (FundraisingBox payloads, pydantic schema) carries over. *Alternative:* Node backend — rejected to avoid rewriting proven logic.

2. **Frontend: Vite + React + TypeScript SPA with Tailwind CSS and shadcn/ui** (Radix-based accessible components), react-hook-form + zod for the review form, TanStack Query for API calls, light/dark via `prefers-color-scheme`. Phone camera capture uses `<input type="file" accept="image/*" capture="environment">` (no custom `getUserMedia` flow needed). The active session id lives in the URL so a reload restores the review step. *Alternatives:* HTMX/Jinja (earlier plan; user wants a polished React app), MUI (heavier, Material look harder to customise), Next.js (SSR not needed; extra runtime), Streamlit (prototype; weak mobile control).

3. **JSON API contract.** `POST /api/sessions` (multipart upload, runs extraction, returns session id + contact + warnings), `GET /api/sessions/{id}` and `GET /api/sessions/{id}/image`, `PUT /api/sessions/{id}` (save edited contact), `GET /api/companies?q=`, `POST /api/sessions/{id}/send`. Errors use a uniform `{code, message}` body. FastAPI serves the built `frontend/dist` as static files with SPA fallback; in development Vite proxies `/api` to FastAPI.

4. **TypeScript types generated from FastAPI's OpenAPI schema** (e.g. `openapi-typescript`), checked in CI for drift, so the pydantic models stay the single source of truth for the API contract.

5. **Extraction via OpenAI-compatible `/chat/completions` with image input, using `httpx`.** Config: `LLM_BASE_URL` (default `https://api.mistral.ai/v1`), `LLM_MODEL` (the cheapest Mistral vision-capable model that is accurate enough on real cards, chosen by the evaluation in task 2.4), `LLM_API_KEY`, `LLM_TIMEOUT`. Mistral's API supports this shape, as do Ollama/LM Studio/vLLM, so switching is config only. **Structured output:** the request uses `response_format: {type: "json_schema", json_schema: {name: "contact", strict: true, schema: …}}` so the endpoint constrains decoding to the schema, which is what makes a small model reliable. The schema is derived from the pydantic `Contact` model but made strict-friendly: every field a string, **all fields listed as required**, `additionalProperties: false`, no defaults (strict modes reject optional fields). If the endpoint answers 400/422 saying the schema format is unsupported (typical for local servers), the client retries once with `response_format: {type: "json_object"}` and remembers that choice for the process lifetime; `LLM_RESPONSE_FORMAT` (`json_schema` default, or `json_object`) forces it. The response is still validated with pydantic and tolerant parsing stays as a defence, since constrained decoding is a provider guarantee we do not control. **Built for a small, cheap model:** one short prompt and a flat schema (all fields strings), temperature 0, a small `max_tokens` cap, the image downscaled before sending to limit input tokens, and at most one retry on malformed JSON, so cost per card stays low and bounded. Only one model is used for the whole extraction. *Alternatives:* Mistral SDK (ties code to one vendor), Mistral OCR + second LLM pass (two calls, more cost; can be added behind the same client interface).

6. **Pydantic `Contact` model is the single source of truth** for API payloads, validation and the extraction JSON schema. The frontend derives its `Contact` type from the generated OpenAPI types and renders fields from one field-config list (label, input type, autocomplete hint), so adding a field touches the model plus that list (pattern adapted from prototype).

7. **Stateless review sessions.** The uploaded image is downscaled (long edge ≈ 1600 px) and kept in an in-memory TTL store keyed by an unguessable session id (e.g. 30 min), together with a per-session `sent` flag and send lock for duplicate protection. Cleared on successful send or expiry. *Alternative:* disk/DB — rejected to honor the no-persistence requirement. Consequence: single-process deployment (documented).

8. **FundraisingBox client isolated in its own module** with explicit mapping function `Contact → person payload` (channel data as `info` lines), `search_companies`, `create_company`, `create_person`, and typed errors (`ConfigError`, `NetworkError`, `ApiError(status, body)`). Reuses the prototype's endpoint, auth and custom-field constants.

9. **Config via environment / `.env`** (`pydantic-settings`), validated at startup; token and API key never rendered or logged. Logging records timings and status codes only, never card content.

10. **Tests:** backend — pytest with `respx` for both external APIs and sample card fixtures, ruff + mypy. Frontend — Vitest + React Testing Library (with MSW for API mocks), ESLint, `tsc --noEmit`, and an axe accessibility check on the main screens.

## Risks / Trade-offs

- [Hosted Mistral sends personal data off-machine] → documented in proposal; endpoint is swappable to a local server; README states the data flow; recommend DPA/consent check.
- [Handwriting accuracy is imperfect] → mandatory review step, empty fields highlighted, no auto-send.
- [FundraisingBox person payload may not accept email/phone/address] → fall back to writing them into `info` until the API fields are confirmed (spec allows either).
- [In-memory sessions lost on restart / not multi-worker] → acceptable for a low-volume internal tool; run a single worker.
- [Duplicate persons already in FundraisingBox] → out of scope beyond company matching; only in-app double-submit is prevented.
- [A small model reads handwriting less accurately and follows the schema less reliably] → mandatory human review, tolerant per-field parsing, one retry, and a documented upgrade path: switching to a larger model is only a `LLM_MODEL` change.
- [Model JSON non-compliance] → structured output where supported, plus tolerant parsing and per-field validation, graceful "incomplete" notice.
- [Provider structured-output support or schema dialect differs (strict mode limits, vision support)] → one automatic fallback to JSON mode, `LLM_RESPONSE_FORMAT` override, and a real-call check on the candidate models in task 2.4.
- [No authentication] → deploy only on trusted network/behind a reverse proxy with auth.
- [Frontend build step adds Node to deployment] → multi-stage Dockerfile builds `frontend/dist` and copies it into the Python image; documented `npm run build` otherwise.
- [API and TS types drifting apart] → generate types from the OpenAPI schema and fail CI on a diff.
- [iPhone photos may arrive as HEIC, which the JPEG/PNG-only rule would reject] → iOS normally converts to JPEG for web uploads; verify on a real iPhone during task 5.2 and, if HEIC does appear, convert client-side or add HEIC to the accepted formats.
- [Camera capture attribute behaves differently across phones] → file picker remains available as fallback; verify on iOS Safari and Android Chrome.
- [Session id in URL could be shared] → ids are unguessable and short-lived; acceptable on a trusted network (see no-auth risk).

## Open Questions

- UI language (German vs English): single fixed language assumed; strings are kept in one module so it can be switched later without changing specs.
- **FundraisingBox API findings (task 3.1, from the official docs at developer.fundraisingbox.com, not yet tried against a live account):**
  - `POST /v1/persons.json` takes only: `last_name` (**the only required field**), `company_id`, `company_name` and `is_company`, `salutation` (`Mr.`, `Mrs.`, `diverse`, `couple`, `family`), `title`, `first_name`, `birthday`, `position`, `info` (max 1000), contact preferences, `greeting`, `external_person_id`, `fb_custom_fields`. `company_name`, `salutation`, `title`, `first_name`, `position` apply only as documented for `is_company` true/false. Success is HTTP 201 with the new `id`; errors are HTTP 400 with an empty `{}` body.
  - Email, phone, address and website are **not** person fields. Each is a separate child call after the person exists, each needing `fb_person_id`: `POST /v1/personEmailAddresses.json` (`email`, `type` home/work/other, `is_main`), `/v1/personPhones.json` (`phone`, `type` home/work/other, `is_main`; there is no "mobile" type), `/v1/personAddresses.json` (`address`, `post_code`, `city`, `state`, `country` as a 2-letter code like `DE`, `type`, `is_main`), `/v1/personWebsites.json` (`url`, `type`, `website_type`).
  - **Decisions taken with the owner:** (1) Email, phone, mobile, address and website are written as labelled lines in the person's `info` text in the single create call, as the prototype does; no child calls, so no half-created person. (2) Company flow: search for the company; if found link via `company_id`; if not found offer to create the company record first and link the person; a card with only a company offers to create just the company record. (3) A company creation followed by a failed person creation is retried without creating the company again (the session keeps the created company id).
  - Open point: whether company records created by the app should also carry the ContactPilot `Sync` custom field. The prototype only set it on persons, so the plan sets it on persons only until the owner says otherwise.
  - **Still unverified (needs a live FundraisingBox account, task 3.4):** the exact request for creating a company record. `last_name` is required on every record and `company_name` is documented only for `is_company=true`, so what `last_name` should hold for a company is unknown; the first guess is `is_company=true`, `company_name` and `last_name` both set to the company name.
  - Salutation values accepted by the API are `Mr.`, `Mrs.`, `diverse`, `couple`, `family`. `info` is limited to 1000 characters, so sending is blocked with a clear message when the lines would not fit.
- Exact Mistral vision model id and whether it supports `json_schema` structured output for image input — confirm at implementation (task 2.4); the JSON-mode fallback is already specified.
