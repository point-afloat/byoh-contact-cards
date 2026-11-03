"""Admin-side account management: list users, invite, re-issue and revoke invitations.

Raw invitation tokens are returned to the admin exactly once, in the response that creates them.
The database keeps only their hash (see app/tokens.py).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.api_errors import ApiError
from app.auth import AuthService, normalize_email
from app.config import Settings
from app.db import Database
from app.models import ROLE_ADMIN, ROLES, TOKEN_INVITE, TOKEN_RESET, Invite, User
from app.timeutil import Clock
from app.tokens import issue_token
from app.validation import EMAIL_MESSAGE, is_valid_email

STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"
STATUS_INVITED = "invited"  # created by an admin, password not chosen yet


def as_utc(value: datetime | None) -> datetime | None:
    """The database holds naive UTC; the API returns aware UTC so browsers read it correctly."""
    return value.replace(tzinfo=UTC) if value is not None else None


def status_of(user: User) -> str:
    if user.password_hash is None:
        return STATUS_INVITED
    return STATUS_ACTIVE if user.is_active else STATUS_INACTIVE


@dataclass(frozen=True)
class UserView:
    id: int
    email: str
    role: str
    status: str
    created_at: datetime
    last_sign_in_at: datetime | None
    invite_expires_at: datetime | None  # of the current invitation, if the user is still pending


@dataclass(frozen=True)
class IssuedInvite:
    user: UserView
    token: str
    expires_at: datetime


def user_not_found() -> ApiError:
    return ApiError(404, "user_not_found", "User not found.")


def _view(user: User, invite_expires_at: datetime | None = None) -> UserView:
    created = as_utc(user.created_at)
    assert created is not None
    return UserView(
        id=user.id,
        email=user.email,
        role=user.role,
        status=status_of(user),
        created_at=created,
        last_sign_in_at=as_utc(user.last_sign_in_at),
        invite_expires_at=as_utc(invite_expires_at) if status_of(user) == STATUS_INVITED else None,
    )


class AccountService:
    def __init__(self, db: Database, settings: Settings, clock: Clock) -> None:
        self._db = db
        self._settings = settings
        self._clock = clock

    def list_users(self) -> list[UserView]:
        with self._db.session() as db:
            current_invites: dict[int, datetime] = {}
            for invite in db.scalars(
                select(Invite).where(
                    Invite.kind == TOKEN_INVITE,
                    Invite.used_at.is_(None),
                    Invite.revoked_at.is_(None),
                )
            ):
                current_invites[invite.user_id] = max(
                    invite.expires_at, current_invites.get(invite.user_id, invite.expires_at)
                )
            users = db.scalars(select(User).order_by(User.id))
            return [_view(user, current_invites.get(user.id)) for user in users]

    def invite(self, email: str, role: str) -> IssuedInvite:
        email = normalize_email(email)
        errors: dict[str, str] = {}
        if not is_valid_email(email):
            errors["email"] = EMAIL_MESSAGE
        if role not in ROLES:
            errors["role"] = "Choose admin or member."
        if errors:
            raise ApiError(422, "validation_error", "Please fix the highlighted fields.", errors)

        exists = ApiError(409, "user_exists", "A user with this email address already exists.")
        with self._db.session() as db:
            if db.scalars(select(User).where(User.email == email)).first() is not None:
                raise exists
            user = User(email=email, role=role, is_active=True, created_at=self._clock())
            db.add(user)
            try:
                db.flush()
            except IntegrityError:  # two admins inviting the same address at once
                raise exists from None
            return self._issue(db, user)

    def reissue_invite(self, user_id: int) -> IssuedInvite:
        """A fresh link for a pending user; every earlier link stops working."""
        with self._db.session() as db:
            user = db.get(User, user_id)
            if user is None:
                raise user_not_found()
            self._require_pending(user)
            return self._issue(db, user)

    def revoke_invite(self, user_id: int) -> None:
        """Withdraw an invitation. The pending user is removed, so the address can be reused."""
        with self._db.session() as db:
            user = db.get(User, user_id)
            if user is None:
                raise user_not_found()
            self._require_pending(user)
            db.delete(user)  # its tokens go with it (ON DELETE CASCADE)

    def update_user(
        self, user_id: int, role: str | None = None, is_active: bool | None = None
    ) -> UserView:
        """Change a user's role and/or switch them off or on. Switching off signs them out."""
        if role is None and is_active is None:
            raise ApiError(422, "validation_error", "Nothing to change.")
        if role is not None and role not in ROLES:
            message = "Choose admin or member."
            raise ApiError(422, "validation_error", message, {"role": message})

        with self._db.session() as db:
            user = db.get(User, user_id)
            if user is None:
                raise user_not_found()
            if is_active is not None and status_of(user) == STATUS_INVITED:
                raise ApiError(
                    409,
                    "user_pending",
                    "This user has not accepted the invitation yet. Revoke the invitation instead.",
                )
            was_active_admin = status_of(user) == STATUS_ACTIVE and user.role == ROLE_ADMIN
            new_role = role if role is not None else user.role
            new_active = is_active if is_active is not None else user.is_active
            if was_active_admin and (new_role != ROLE_ADMIN or not new_active):
                if self._other_active_admins(db, user.id) == 0:
                    raise ApiError(
                        409,
                        "last_admin",
                        "At least one active administrator is needed. "
                        "Make someone else an administrator first.",
                    )
            user.role = new_role
            user.is_active = new_active
            if not new_active:
                AuthService.end_user_sessions(db, user.id)  # signed out on their next request
            return _view(user)

    def issue_reset_link(self, user_id: int) -> IssuedInvite:
        """A single-use password-reset link for an active user. It signs them out when used."""
        with self._db.session() as db:
            user = db.get(User, user_id)
            if user is None:
                raise user_not_found()
            if status_of(user) == STATUS_INVITED:
                raise ApiError(
                    409,
                    "user_pending",
                    "This user has no password yet. Send a new invitation instead.",
                )
            if status_of(user) == STATUS_INACTIVE:
                raise ApiError(
                    409, "user_inactive", "Reactivate this user before issuing a reset link."
                )
            ttl = timedelta(minutes=self._settings.auth_reset_ttl_minutes)
            return self._issue(db, user, TOKEN_RESET, ttl)

    @staticmethod
    def _other_active_admins(db: DbSession, excluding_user_id: int) -> int:
        return (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.role == ROLE_ADMIN,
                    User.is_active.is_(True),
                    User.password_hash.is_not(None),
                    User.id != excluding_user_id,
                )
            )
            or 0
        )

    def _issue(
        self, db: DbSession, user: User, kind: str = TOKEN_INVITE, ttl: timedelta | None = None
    ) -> IssuedInvite:
        ttl = ttl or timedelta(hours=self._settings.auth_invite_ttl_hours)
        raw, row = issue_token(db, user.id, kind, ttl, self._clock())
        expires = as_utc(row.expires_at)
        assert expires is not None
        return IssuedInvite(user=_view(user, row.expires_at), token=raw, expires_at=expires)

    @staticmethod
    def _require_pending(user: User) -> None:
        if status_of(user) != STATUS_INVITED:
            raise ApiError(
                409,
                "user_not_pending",
                "This user already has a password. Issue a password reset link instead.",
            )
