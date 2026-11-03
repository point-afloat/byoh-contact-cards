"""Readiness problems for the health check and the startup log.

Messages name settings and paths, never values, so they are safe to log and to return.
"""

import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import text

from app.config import Settings
from app.db import Database
from app.errors import ConfigError
from app.services import ensure_services


def data_dir_problem(path: Path) -> str | None:
    if not path.is_dir():
        return f"DATA_DIR {path} does not exist or is not a directory"
    try:
        with tempfile.NamedTemporaryFile(dir=path):  # create-and-delete write probe
            pass
    except OSError:
        return f"DATA_DIR {path} is not writable"
    return None


logger = logging.getLogger(__name__)


def database_problem(db: Database) -> str | None:
    if not db.path.is_file():  # do not let a health check create the file
        return "The user database has not been initialised"
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM users LIMIT 1"))
    except Exception:
        return "The user database is not available (the migration did not complete)"
    return None


def settings_problems(settings: Settings) -> list[str]:
    problems: list[str] = []
    if settings.fundraisingbox_apitoken is None:
        problems.append("FUNDRAISINGBOX_APITOKEN is not set")
    problem = data_dir_problem(settings.data_dir)
    if problem:
        problems.append(problem)
    return problems


def health_problems(app: FastAPI) -> list[str]:
    """Everything that makes this deployment unhealthy; empty when it is ready."""
    try:
        services = ensure_services(app)
    except ConfigError as exc:  # names the missing or invalid variables only
        return [str(exc)]
    problems = settings_problems(services.settings)
    if not data_dir_problem(services.settings.data_dir):
        problem = database_problem(services.db)
        if problem:
            problems.append(problem)
        else:
            problems.extend(services.auth.initial_admin_problems())
    return problems


def prepare_on_startup(app: FastAPI) -> list[str]:
    """Run startup work (database migration) and return every problem found, for the log."""
    try:
        services = ensure_services(app)
    except ConfigError as exc:
        return [str(exc)]
    if not data_dir_problem(services.settings.data_dir):
        try:
            services.db.migrate()
            services.auth.bootstrap_admin()
        except Exception:
            logger.exception("Database startup failed")  # no secrets in these errors
    return health_problems(app)
