from pathlib import Path

import pytest
from sqlalchemy import select

from app.db import Database
from app.models import User
from app.passwords import (
    DUMMY_HASH,
    MAX_LENGTH,
    MIN_LENGTH,
    hash_password,
    needs_rehash,
    validate_password,
    verify_password,
)
from app.timeutil import utcnow

GOOD = "correct horse battery"


def test_hashes_are_argon2id_and_salted() -> None:
    first, second = hash_password(GOOD), hash_password(GOOD)
    assert first.startswith("$argon2id$")
    assert first != second  # a fresh salt every time
    assert GOOD not in first


def test_verify_accepts_the_right_password_only() -> None:
    hashed = hash_password(GOOD)
    assert verify_password(GOOD, hashed) is True
    assert verify_password(GOOD + "x", hashed) is False
    assert verify_password("", hashed) is False


@pytest.mark.parametrize("garbage", ["", "not-a-hash", "$argon2id$broken", "$2b$12$abc"])
def test_a_malformed_stored_hash_never_matches_and_never_raises(garbage: str) -> None:
    assert verify_password(GOOD, garbage) is False


def test_the_dummy_hash_is_a_real_hash_that_matches_nothing_useful() -> None:
    assert DUMMY_HASH.startswith("$argon2id$")
    assert verify_password(GOOD, DUMMY_HASH) is False


def test_freshly_made_hashes_do_not_need_rehashing() -> None:
    assert needs_rehash(hash_password(GOOD)) is False


def test_the_minimum_length_is_twelve_characters() -> None:
    assert MIN_LENGTH == 12
    assert validate_password("a1b2c3d4e5f") is not None  # 11 characters
    assert validate_password("a1b2c3d4e5f6") is None  # 12 characters
    assert "12" in str(validate_password("short"))


def test_no_composition_rules_so_a_passphrase_is_fine() -> None:
    assert validate_password("only lowercase words here") is None


@pytest.mark.parametrize(
    "common", ["password1234", "PASSWORD12345", "Qwertyuiop12", "administrator"]
)
def test_common_passwords_are_rejected_regardless_of_case(common: str) -> None:
    assert "easy to guess" in str(validate_password(common))


def test_a_single_repeated_character_is_rejected() -> None:
    assert validate_password("x" * 20) is not None


def test_the_password_must_not_be_the_email() -> None:
    assert validate_password("anna.meier@example.org", email="Anna.Meier@example.org") is not None
    assert validate_password("annameier.long", email="annameier.long@example.org") is not None
    assert validate_password("a different phrase", email="anna.meier@example.org") is None


def test_absurdly_long_passwords_are_rejected() -> None:
    assert validate_password("ab" * (MAX_LENGTH // 2 + 1)) is not None


def test_no_plaintext_password_reaches_the_database(tmp_path: Path) -> None:
    db = Database(tmp_path)
    db.migrate()
    secret = "my very secret passphrase"
    with db.session() as session:
        session.add(
            User(
                email="u@example.org",
                password_hash=hash_password(secret),
                role="member",
                is_active=True,
                created_at=utcnow(),
            )
        )
    db.engine.dispose()
    assert secret.encode() not in db.path.read_bytes()
    reopened = Database(tmp_path)
    with reopened.session() as session:
        stored = session.scalars(select(User.password_hash)).one()
    assert stored is not None and stored.startswith("$argon2id$") and secret not in stored
