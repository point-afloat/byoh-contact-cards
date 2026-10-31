# Spec Delta

## Purpose

Defines how the application behaves when run as a Docker container on Sliplane: how it binds, reports health, receives configuration, and shuts down.

## ADDED Requirements

### Requirement: Self-contained container image
The system SHALL be buildable into a single Docker image from the repository that contains the built frontend and the backend, and starts the complete app without any additional build or install step at runtime.

#### Scenario: Build and run
- **WHEN** the image is built from a clean checkout and started with the required environment variables
- **THEN** the app serves the web interface and API from the container

#### Scenario: No secrets in image
- **WHEN** the built image and its layers are inspected
- **THEN** they contain no API tokens, passwords, or `.env` files

### Requirement: Port binding from environment
The system SHALL listen on all interfaces on the port given by the `PORT` environment variable, defaulting to 8080 when it is not set.

#### Scenario: Port provided
- **WHEN** the container starts with `PORT=9000`
- **THEN** the app accepts requests on port 9000

#### Scenario: Port not provided
- **WHEN** the container starts without `PORT`
- **THEN** the app accepts requests on port 8080

### Requirement: Health endpoint
The system SHALL expose a health endpoint that returns a 2xx response without authentication once the app is running with valid configuration, and a non-2xx response when required configuration is missing.

#### Scenario: Healthy
- **WHEN** a request is made to the health endpoint of a correctly configured running container
- **THEN** the response status is 2xx and the body contains no secrets or card data

#### Scenario: Misconfigured
- **WHEN** a required setting such as the model endpoint API key or FundraisingBox token is missing
- **THEN** the health endpoint reports failure and the problem is named in the container log without printing secret values

### Requirement: Environment-based configuration
The system SHALL read all deployment settings (model endpoint, model name, API keys, FundraisingBox token, upload limit, session lifetime) from environment variables.

#### Scenario: Setting changed without rebuild
- **WHEN** an environment variable is changed and the container is restarted
- **THEN** the new value takes effect without rebuilding the image

### Requirement: Persistent data directory
The system SHALL store persistent application data (user accounts, invites, sessions) only under the directory given by `DATA_DIR`, defaulting to `/data`, SHALL keep that data across container restarts and redeploys when the directory is a mounted volume, and SHALL NOT store card images or contact data there.

#### Scenario: Redeploy keeps users
- **WHEN** the container is replaced by a new version with the same volume mounted at `DATA_DIR`
- **THEN** existing user accounts are still present

#### Scenario: Directory not writable
- **WHEN** `DATA_DIR` is missing or not writable by the app user
- **THEN** startup fails with a clear log message and the health endpoint reports failure

#### Scenario: Card data not persisted
- **WHEN** the contents of `DATA_DIR` are inspected after cards were processed
- **THEN** they contain no card images or extracted contact data

### Requirement: Unprivileged, single-process runtime
The system SHALL run as a non-root user in a single application process, so that the in-memory sessions are consistent.

#### Scenario: User check
- **WHEN** the running container is inspected
- **THEN** the application process is not running as root and only one worker serves requests

### Requirement: Logging and shutdown
The system SHALL write logs to standard output and standard error without card contents or credentials, and SHALL stop cleanly on a termination signal.

#### Scenario: Redeploy
- **WHEN** the container receives a termination signal during a redeploy
- **THEN** it stops within a short grace period and in-flight requests are completed or fail cleanly

#### Scenario: Sessions lost on restart
- **WHEN** a user continues a review session after the container restarted
- **THEN** the user is told the session expired and can scan the card again
