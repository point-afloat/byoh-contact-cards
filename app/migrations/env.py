"""Alembic environment: runs migrations against the URL passed in by app.db.Database."""

from alembic import context
from sqlalchemy import create_engine

from app.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(config.get_main_option("sqlalchemy.url") or "")
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
