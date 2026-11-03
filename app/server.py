"""Process entrypoint for the container: `python -m app.server`.

Listens on all interfaces on $PORT (default 8080) with a single worker, because review
sessions live in memory. uvicorn handles SIGTERM with a graceful shutdown.
"""

import logging
import os
from collections.abc import Mapping

import uvicorn

from app.errors import ConfigError

DEFAULT_PORT = 8080
GRACEFUL_SHUTDOWN_SECONDS = 10


def port_from_env(env: Mapping[str, str] | None = None) -> int:
    values = os.environ if env is None else env
    raw = values.get("PORT", "").strip()
    if not raw:
        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError:
        raise ConfigError(f"PORT must be a number, got {raw!r}") from None
    if not 1 <= port <= 65535:
        raise ConfigError(f"PORT must be between 1 and 65535, got {port}")
    return port


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        port = port_from_env()
    except ConfigError as exc:
        raise SystemExit(f"error: {exc}") from None
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104 - the container must accept connections from outside
        port=port,
        workers=1,
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS,
    )


if __name__ == "__main__":
    main()
