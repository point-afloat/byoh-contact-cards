"""SQLite database under DATA_DIR: engine, sessions and schema migrations (Alembic)."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

DB_FILENAME = "app.db"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class Database:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / DB_FILENAME
        self.url = f"sqlite:///{self.path}"
        # Requests run in a threadpool, so connections may be used from several threads.
        self.engine: Engine = create_engine(self.url, connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _configure_connection)

    def migrate(self) -> None:
        """Bring the schema up to date. Creates the database file on first use."""
        config = Config()
        config.set_main_option("script_location", str(MIGRATIONS_DIR))
        config.set_main_option("sqlalchemy.url", self.url.replace("%", "%%"))
        command.upgrade(config, "head")

    @contextmanager
    def session(self) -> Iterator[Session]:
        """A unit of work: committed on success, rolled back on any error."""
        with Session(self.engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise


def _configure_connection(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
