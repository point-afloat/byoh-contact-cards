import sqlite3
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.db import Database
from app.models import Base, Invite, User
from app.timeutil import utcnow


def make_user(email: str = "a@example.org") -> User:
    return User(email=email, role="member", is_active=True, created_at=utcnow())


def test_a_fresh_directory_is_migrated_with_all_tables(tmp_path: Path) -> None:
    db = Database(tmp_path)
    db.migrate()
    assert db.path.is_file()
    assert set(inspect(db.engine).get_table_names()) >= {
        "users",
        "invites",
        "sessions",
        "login_attempts",
        "alembic_version",
    }


def test_data_survives_a_restart(tmp_path: Path) -> None:
    first = Database(tmp_path)
    first.migrate()
    with first.session() as session:
        session.add(make_user("keep@example.org"))
    first.engine.dispose()

    restarted = Database(tmp_path)
    restarted.migrate()  # running migrations again must be harmless
    with restarted.session() as session:
        assert session.scalars(select(User.email)).all() == ["keep@example.org"]


def test_migrations_match_the_models_exactly(tmp_path: Path) -> None:
    db = Database(tmp_path)
    db.migrate()
    with db.engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], f"models and migration disagree: {diff}"


def test_emails_are_unique(tmp_path: Path) -> None:
    db = Database(tmp_path)
    db.migrate()
    with pytest.raises(IntegrityError), db.session() as session:
        session.add_all([make_user("dup@example.org"), make_user("dup@example.org")])


def test_foreign_keys_are_enforced_and_cascade(tmp_path: Path) -> None:
    db = Database(tmp_path)
    db.migrate()
    now = utcnow()
    with pytest.raises(IntegrityError), db.session() as session:  # invite for a missing user
        session.add(
            Invite(user_id=999, kind="invite", token_hash="x", created_at=now, expires_at=now)
        )

    with db.session() as session:
        user = make_user()
        session.add(user)
        session.flush()
        session.add(
            Invite(user_id=user.id, kind="invite", token_hash="h", created_at=now, expires_at=now)
        )
    with db.session() as session:
        session.delete(session.scalars(select(User)).one())
    with db.session() as session:
        assert session.scalars(select(Invite)).all() == []  # removed with the user


def test_a_failed_unit_of_work_is_rolled_back(tmp_path: Path) -> None:
    db = Database(tmp_path)
    db.migrate()
    with pytest.raises(RuntimeError), db.session() as session:
        session.add(make_user("ghost@example.org"))
        session.flush()
        raise RuntimeError("boom")
    with db.session() as session:
        assert session.scalars(select(User)).all() == []


def test_the_database_file_only_holds_account_tables(tmp_path: Path) -> None:
    db = Database(tmp_path)
    db.migrate()
    with sqlite3.connect(db.path) as raw:
        names = {r[0] for r in raw.execute("select name from sqlite_master where type='table'")}
    assert not {n for n in names if "card" in n or "contact" in n or "image" in n}
