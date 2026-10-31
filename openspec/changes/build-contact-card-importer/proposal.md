# Proposal

## Why

About 100 paper contact cards (mixed handwritten and printed) are collected at events each month and typed into FundraisingBox by hand. The `../contact_cards` prototype showed that vision-model extraction plus a human review step works, but it was built around local engines, a Streamlit UI and ad-hoc FundraisingBox calls. This change rebuilds it as a maintainable app with a swappable model endpoint (Mistral first) and a reliable path from scanned card to FundraisingBox person.

## What Changes

- New mobile-first React + TypeScript single-page app (polished, accessible, light/dark) to scan with a phone camera or upload a contact card image (JPEG or PNG). The Python backend exposes a JSON API and serves the built app.
- Extraction of card contents into a fixed structured contact schema using a vision-capable LLM reached through a configurable OpenAI-compatible endpoint (base URL, model name, API key). Default configuration targets Mistral; switching provider is a configuration change only.
- Mandatory human review screen: image shown next to editable fields, validation of required fields, optional match against existing FundraisingBox companies.
- Submission of the confirmed contact to FundraisingBox via its persons API, with clear success/failure feedback, retry of failed sends, and protection against accidental duplicate submission.
- Secrets and endpoint settings come from environment configuration; nothing is hard-coded.

## Capabilities

### New Capabilities
- `card-extraction`: turning an uploaded card image into structured contact fields through a replaceable model endpoint.
- `contact-review`: human review and correction of extracted fields, including company matching, before anything is sent.
- `fundraisingbox-export`: mapping a confirmed contact to a FundraisingBox person, sending it, and reporting/handling outcomes.
- `scan-ui`: the responsive, accessible, visually consistent scan → review → done experience across phone and desktop.

### Modified Capabilities
<!-- None: openspec/specs is empty. -->

## Impact

- New code in this repository (greenfield); no existing behavior changes: a Python backend (JSON API) and a `frontend/` React + TypeScript app. Node.js/npm becomes a build-time requirement.
- External systems: a Mistral (or other OpenAI-compatible) vision endpoint and the FundraisingBox REST API (`https://api.fundraisingbox.com/v1/persons.json`, basic auth with API token).
- **Privacy**: card contents are personal data. With a hosted Mistral endpoint the card image leaves the machine (unlike the fully local prototype); the endpoint stays swappable so a local model can be used instead. Data-processing agreement / consent for the hosted option is the owner's responsibility.
- Reference only: field mapping, the ContactPilot custom field (id 16786) and the company-based donor model are carried over from the prototype's `src/fundraisingbox/`.

## Assumptions

- Stack: Python 3.12 + FastAPI (JSON API, uv) for the backend; Vite + React + TypeScript + Tailwind + shadcn/ui for the frontend, as requested by the user (see design.md).
- Single-user/internal tool behind trusted network access; no user accounts in this change.
- PDF upload is not supported (not needed currently); only JPEG and PNG images are accepted. PDF support could be added later as a separate change.
- Out of scope: batch/bulk upload, storing cards or contacts persistently, updating existing FundraisingBox persons, user authentication.
