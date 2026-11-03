from datetime import timedelta
from pathlib import Path

import pytest

from app.db import Database
from app.models import TOKEN_INVITE, TOKEN_RESET, User
from app.timeutil import utcnow
from app.tokens import consume_token, hash_token, issue_token, new_token, peek_token

NOW = utcnow()
WEEK = timedelta(days=7)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path)
    database.migrate()
    with database.session() as session:
        session.add(User(email="u@example.org", role="member", is_active=True, created_at=NOW))
    return database


def test_tokens_are_long_random_and_url_safe() -> None:
    tokens = {new_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 43 and t.replace("-", "").replace("_", "").isalnum() for t in tokens)


def test_the_stored_value_is_a_sha256_hash_not_the_token(db: Database) -> None:
    with db.session() as session:
        raw, row = issue_token(session, 1, TOKEN_INVITE, WEEK, NOW)
        assert row.token_hash == hash_token(raw) and len(row.token_hash) == 64
        assert row.token_hash != raw
    db.engine.dispose()
    assert raw.encode() not in db.path.read_bytes()  # no usable token in the database file


def test_a_token_works_exactly_once(db: Database) -> None:
    with db.session() as session:
        raw, _ = issue_token(session, 1, TOKEN_INVITE, WEEK, NOW)
    with db.session() as session:
        first = consume_token(session, raw, NOW)
        assert first is not None and first.used_at == NOW and first.user_id == 1
    with db.session() as session:
        assert consume_token(session, raw, NOW) is None  # reuse
        assert peek_token(session, raw, NOW) is None


def test_it_expires_after_its_lifetime(db: Database) -> None:
    with db.session() as session:
        raw, row = issue_token(session, 1, TOKEN_RESET, timedelta(hours=1), NOW)
        assert row.expires_at == NOW + timedelta(hours=1)
    with db.session() as session:
        assert peek_token(session, raw, NOW + timedelta(minutes=59)) is not None
        assert consume_token(session, raw, NOW + timedelta(hours=1)) is None  # at the deadline
    with db.session() as session:
        # an expired token was not used up by the failed attempt
        assert session.get(User, 1) is not None


def test_issuing_a_new_token_invalidates_the_earlier_ones(db: Database) -> None:
    with db.session() as session:
        old, _ = issue_token(session, 1, TOKEN_INVITE, WEEK, NOW)
        new, _ = issue_token(session, 1, TOKEN_INVITE, WEEK, NOW + timedelta(minutes=1))
    with db.session() as session:
        assert consume_token(session, old, NOW + timedelta(minutes=2)) is None
        assert consume_token(session, new, NOW + timedelta(minutes=2)) is not None


def test_a_reset_token_also_invalidates_a_pending_invite(db: Database) -> None:
    with db.session() as session:
        invite, _ = issue_token(session, 1, TOKEN_INVITE, WEEK, NOW)
        reset, _ = issue_token(session, 1, TOKEN_RESET, timedelta(hours=1), NOW)
    with db.session() as session:
        assert peek_token(session, invite, NOW) is None
        assert peek_token(session, reset, NOW) is not None


@pytest.mark.parametrize("bad", ["", "nope", "a" * 43, " "])
def test_unknown_tokens_never_work(db: Database, bad: str) -> None:
    with db.session() as session:
        assert peek_token(session, bad, NOW) is None
        assert consume_token(session, bad, NOW) is None


def test_peeking_does_not_use_the_token_up(db: Database) -> None:
    with db.session() as session:
        raw, _ = issue_token(session, 1, TOKEN_INVITE, WEEK, NOW)
    with db.session() as session:
        assert peek_token(session, raw, NOW) is not None
        assert peek_token(session, raw, NOW) is not None
        assert consume_token(session, raw, NOW) is not None


def test_a_token_belongs_to_its_user_and_kind(db: Database) -> None:
    with db.session() as session:
        raw, _ = issue_token(session, 1, TOKEN_RESET, timedelta(hours=1), NOW)
    with db.session() as session:
        row = consume_token(session, raw, NOW)
        assert row is not None and (row.user_id, row.kind) == (1, TOKEN_RESET)
