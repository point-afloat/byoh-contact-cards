# Proposal

## Why

The contact card importer (change `build-contact-card-importer`) must run as a Docker container hosted on Sliplane so staff can use it from a phone without anyone running it locally. The container must follow Sliplane's runtime contract (port, health check, env vars) and keep the small amount of persistent data that user accounts need (change `add-user-accounts`) on a mounted volume.

## What Changes

- Production container image that builds the React frontend and runs the FastAPI backend serving it, listening on the port Sliplane provides, running as a non-root user, with a reproducible build.
- Unauthenticated health endpoint suitable for Sliplane's health check, answering only after the app is configured and ready.
- Configuration entirely through environment variables set in Sliplane (no secrets in the image or repository).
- A single public service: the app itself, protected by its own login (see `add-user-accounts`). No proxy service is used.
- A persistent data directory (`DATA_DIR`) that is expected to be a mounted Sliplane volume, so users survive redeploys; card data stays in memory only.
- Single-worker run mode that fits the in-memory review sessions, with graceful behavior on redeploy (review sessions are lost, users are told to rescan).
- Deployment documentation: step-by-step Sliplane setup (repo/Dockerfile deploy, env vars, volume, health check) and local `docker run` instructions.

## Capabilities

### New Capabilities
- `container-deployment`: runtime contract of the container image: port binding, health check, environment-based configuration, persistent data directory, non-root execution, logging to stdout, and safe shutdown.

### Modified Capabilities
<!-- None: openspec/specs is empty. -->

## Impact

- Adds `Dockerfile`, `.dockerignore`, deployment docs and a `docker-compose.yml` for local parity; small backend changes for `PORT` handling and the health endpoint.
- Extends task 6.1 of `build-contact-card-importer` (basic multi-stage Dockerfile); this change takes ownership of container details. Depends on `build-contact-card-importer` and is applied together with `add-user-accounts`, which supplies the authentication that makes a public URL acceptable. Do not expose the service publicly before both are in place.
- External: Sliplane (container hosting, Git/registry deploy, health checks, volumes).
- Security: with the proxy gone, the app's own login is the only access barrier; the health endpoint must expose nothing sensitive.
- Privacy: card images exist only in memory inside the container. The volume holds only user accounts, invites and sessions.

## Assumptions

- Sliplane builds from the Git repository's Dockerfile (a registry image would also work).
- Sliplane supports attaching a persistent volume to the service; exact mount steps are taken from its documentation at implementation time (its docs search result was thin on volumes).
- Out of scope: custom domain setup, CI/CD, autoscaling or multiple replicas, authentication logic (handled by `add-user-accounts`).
