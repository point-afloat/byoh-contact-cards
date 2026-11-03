"""Password rules and hashing (argon2id with the library's defaults)."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_LENGTH = 12
MAX_LENGTH = 1024  # keeps hashing time bounded for absurd inputs

# A deliberately small list: anything shorter than MIN_LENGTH is rejected by length anyway.
COMMON_PASSWORDS = frozenset(
    {
        "password1234", "password12345", "passwordpassword", "passwort12345", "1234567890123",
        "123456789012", "qwertyuiopas", "qwertyuiop12", "qwertz123456", "iloveyou1234",
        "administrator", "letmein123456", "welcome12345", "willkommen123", "changeme1234",
        "changemechangeme", "abcdefghijkl", "hallo12345678", "correcthorsebatterystaple",
    }
)  # fmt: skip

_hasher = PasswordHasher()


def validate_password(password: str, *, email: str | None = None) -> str | None:
    """Return a message telling the user what to change, or None when the password is acceptable."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    lowered = password.casefold()
    if lowered in COMMON_PASSWORDS or len(set(password)) == 1:
        return "This password is too easy to guess. Choose a different one."
    if email:
        address = email.casefold()
        if lowered in (address, address.split("@")[0]):
            return "The password must not be your email address."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True only for a matching password; any malformed hash or mismatch is simply False."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# Verified against when the email is unknown, so unknown and known emails cost the same time.
DUMMY_HASH = hash_password(secrets.token_urlsafe(24))
