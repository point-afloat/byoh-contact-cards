"""Accounts: sessions, sign-in with throttling, password changes and the first administrator.

Passwords are only ever stored as argon2id hashes, session cookies only as SHA-256 hashes, and
nothing secret is logged.
"""

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from app.api_errors import ApiError
from app.config import Settings
from app.db import Database
from app.models import ROLE_ADMIN, TOKEN_INVITE, AuthSession, Invite, LoginAttempt, User
from app.passwords import (
    DUMMY_HASH,
    hash_password,
    needs_rehash,
    validate_password,
    verify_password,
)
from app.timeutil import Clock
from app.tokens import consume_token, hash_token, peek_token
from app.validation import is_valid_email

logger = logging.getLogger(__name__)

COOKIE_NAME = "session"
FAILURE_WINDOW = timedelta(minutes=10)
# Sign-in is refused, even with the right password, when any of these is reached in the window.
MAX_FAILURES_PER_EMAIL_AND_IP = 5  # one person guessing at one account from one place
MAX_FAILURES_PER_EMAIL = 30  # guessing at one account from many places (a backstop)
MAX_FAILURES_PER_IP = 20  # one place trying many accounts
LAST_SEEN_REFRESH = timedelta(minutes=1)  # do not write on every request


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass(frozen=True)
class AuthUser:
    id: int
    email: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


def invalid_credentials() -> ApiError:
    return ApiError(401, "invalid_credentials", "Email or password incorrect.")


def invite_invalid() -> ApiError:
    return ApiError(
        400,
        "invite_invalid",
        "This link is no longer valid. Ask an administrator for a new one.",
    )


def too_many_attempts() -> ApiError:
    return ApiError(429, "too_many_attempts", "Too many failed attempts. Please try again later.")


class AuthService:
    def __init__(self, db: Database, settings: Settings, clock: Clock) -> None:
        self._db = db
        self._settings = settings
        self._clock = clock

    # ---- sessions ------------------------------------------------------------------------
    def create_session(self, db: DbSession, user_id: int) -> str:
        """Open a session and return the raw cookie value (only its hash is stored)."""
        raw = secrets.token_urlsafe(32)
        now = self._clock()
        db.add(
            AuthSession(
                token_hash=hash_token(raw),
                user_id=user_id,
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(days=self._settings.auth_session_days),
            )
        )
        return raw

    def authenticate(self, raw: str | None) -> AuthUser | None:
        """The signed-in user for a session cookie, or None (unknown, expired, deactivated)."""
        if not raw:
            return None
        now = self._clock()
        idle = timedelta(hours=self._settings.auth_session_idle_hours)
        with self._db.session() as db:
            row = db.scalars(
                select(AuthSession).where(AuthSession.token_hash == hash_token(raw))
            ).first()
            if row is None:
                return None
            user = db.get(User, row.user_id)
            if (
                row.expires_at <= now
                or row.last_seen_at + idle <= now
                or user is None
                or not user.is_active
                or user.password_hash is None
            ):
                db.delete(row)
                return None
            if now - row.last_seen_at >= LAST_SEEN_REFRESH:
                row.last_seen_at = now
            return AuthUser(user.id, user.email, user.role)

    def end_session(self, raw: str | None) -> None:
        if raw:
            with self._db.session() as db:
                db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(raw)))

    @staticmethod
    def end_user_sessions(db: DbSession, user_id: int, keep_raw: str | None = None) -> None:
        """Sign a user out everywhere, optionally keeping one session (the current one)."""
        statement = delete(AuthSession).where(AuthSession.user_id == user_id)
        if keep_raw:
            statement = statement.where(AuthSession.token_hash != hash_token(keep_raw))
        db.execute(statement)

    # ---- throttling ----------------------------------------------------------------------
    @staticmethod
    def _failures(
        db: DbSession, since: datetime, *, email: str | None = None, ip: str | None = None
    ) -> int:
        """Failed attempts since `since`, for an email, an address, or both together."""
        query = (
            select(func.count()).select_from(LoginAttempt).where(LoginAttempt.attempted_at > since)
        )
        if email is not None:
            query = query.where(LoginAttempt.email == email)
        if ip is not None:
            query = query.where(LoginAttempt.ip == ip)
        return db.scalar(query) or 0

    def _is_blocked(self, db: DbSession, email: str, ip: str) -> bool:
        since = self._clock() - FAILURE_WINDOW
        return (
            self._failures(db, since, email=email, ip=ip) >= MAX_FAILURES_PER_EMAIL_AND_IP
            or self._failures(db, since, email=email) >= MAX_FAILURES_PER_EMAIL
            or self._failures(db, since, ip=ip) >= MAX_FAILURES_PER_IP
        )

    def _record_failure(self, db: DbSession, email: str, ip: str) -> None:
        db.add(LoginAttempt(email=email, ip=ip, attempted_at=self._clock()))

    # ---- sign in -------------------------------------------------------------------------
    def login(self, email: str, password: str, ip: str) -> tuple[AuthUser, str]:
        """Check credentials. Raises 401 (always the same message) or 429 when throttled."""
        email = normalize_email(email)
        with self._db.session() as db:
            if self._is_blocked(db, email, ip):  # refused attempts are not counted again
                raise too_many_attempts()
            user = db.scalars(select(User).where(User.email == email)).first()
            stored = user.password_hash if user is not None and user.is_active else None
            # Always verify against *some* hash so an unknown email costs the same time.
            matches = verify_password(password, stored or DUMMY_HASH)
            if user is not None and stored is not None and matches:
                if needs_rehash(stored):
                    user.password_hash = hash_password(password)
                user.last_sign_in_at = self._clock()
                # Only this person's failures from this place: failures from other addresses
                # (someone else guessing) must keep counting.
                db.execute(
                    delete(LoginAttempt).where(LoginAttempt.email == email, LoginAttempt.ip == ip)
                )
                raw = self.create_session(db, user.id)
                return AuthUser(user.id, user.email, user.role), raw
            self._record_failure(db, email, ip)
        raise invalid_credentials()  # raised after the failure row was committed

    # ---- password change -----------------------------------------------------------------
    def change_password(
        self, user_id: int, current: str, new: str, ip: str, keep_session_raw: str | None
    ) -> None:
        wrong_password = False
        with self._db.session() as db:
            user = db.get(User, user_id)
            if user is None or user.password_hash is None:
                raise invalid_credentials()
            if self._is_blocked(db, user.email, ip):
                raise too_many_attempts()
            if not verify_password(current, user.password_hash):
                self._record_failure(db, user.email, ip)  # guessing here is throttled like sign-in
                wrong_password = True
            else:
                message = validate_password(new, email=user.email)
                if message:
                    raise ApiError(422, "validation_error", message, {"new_password": message})
                user.password_hash = hash_password(new)
                self.end_user_sessions(db, user.id, keep_raw=keep_session_raw)
        if wrong_password:
            text = "The current password is incorrect."
            raise ApiError(400, "wrong_password", text, {"current_password": text})

    # ---- accepting an invitation or a password-reset link ---------------------------------
    @staticmethod
    def _token_fits_user(row: Invite, user: User | None) -> bool:
        """An invitation is for someone without a password yet, a reset for someone with one."""
        if user is None or not user.is_active:
            return False
        pending = user.password_hash is None
        return pending if row.kind == TOKEN_INVITE else not pending

    def invite_info(self, token: str) -> tuple[str, str]:
        """(email, kind) for a link that is still usable, without using it up."""
        with self._db.session() as db:
            row = peek_token(db, token, self._clock())
            user = db.get(User, row.user_id) if row is not None else None
            if row is None or not self._token_fits_user(row, user) or user is None:
                raise invite_invalid()
            return user.email, row.kind

    def accept_token(self, token: str, password: str) -> tuple[AuthUser, str]:
        """Set the password a link was issued for, use the link up and sign the person in."""
        now = self._clock()
        with self._db.session() as db:
            row = peek_token(db, token, now)
            user = db.get(User, row.user_id) if row is not None else None
            if row is None or not self._token_fits_user(row, user) or user is None:
                raise invite_invalid()
            # Check the password first, so a weak one does not burn the link.
            message = validate_password(password, email=user.email)
            if message:
                raise ApiError(422, "validation_error", message, {"password": message})
            consumed = consume_token(db, token, now)  # single use, even if two requests race
            if consumed is None:
                raise invite_invalid()
            user.password_hash = hash_password(password)
            user.last_sign_in_at = now
            if consumed.kind != TOKEN_INVITE:  # a reset signs the person out everywhere else
                self.end_user_sessions(db, user.id)
            raw = self.create_session(db, user.id)
            return AuthUser(user.id, user.email, user.role), raw

    # ---- first administrator -------------------------------------------------------------
    def user_count(self) -> int:
        with self._db.session() as db:
            return db.scalar(select(func.count()).select_from(User)) or 0

    def initial_admin_problems(self) -> list[str]:
        """Why the first administrator cannot be created (names only, never values)."""
        if self.user_count() > 0:
            return []
        s = self._settings
        if not s.initial_admin_email or s.initial_admin_password is None:
            return [
                "No users exist yet: set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD "
                "to create the first administrator"
            ]
        problems: list[str] = []
        if not is_valid_email(normalize_email(s.initial_admin_email)):
            problems.append("INITIAL_ADMIN_EMAIL is not a valid email address")
        message = validate_password(
            s.initial_admin_password.get_secret_value(),
            email=normalize_email(s.initial_admin_email),
        )
        if message:
            problems.append(f"INITIAL_ADMIN_PASSWORD does not meet the password rules: {message}")
        return problems

    def bootstrap_admin(self) -> bool:
        """Create the first administrator when no user exists. Ignored once any user exists."""
        s = self._settings
        with self._db.session() as db:
            if (db.scalar(select(func.count()).select_from(User)) or 0) > 0:
                return False
            if (
                self.initial_admin_problems()
                or not s.initial_admin_email
                or not s.initial_admin_password
            ):
                return False
            email = normalize_email(s.initial_admin_email)
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(s.initial_admin_password.get_secret_value()),
                    role=ROLE_ADMIN,
                    is_active=True,
                    created_at=self._clock(),
                )
            )
        logger.info("Created the first administrator account")
        return True
