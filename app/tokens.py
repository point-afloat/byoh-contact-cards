"""Random single-use tokens for invitations and password resets.

Only the SHA-256 of a token is stored (tokens are 256 bits of randomness, so a fast hash is
enough). The raw token is shown once to the admin and never written to the database or logs.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Invite

TOKEN_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def revoke_tokens(session: Session, user_id: int, now: datetime) -> None:
    """Invalidate every unused token of a user (used when a new one is issued)."""
    session.execute(
        update(Invite)
        .where(Invite.user_id == user_id, Invite.used_at.is_(None), Invite.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def issue_token(
    session: Session, user_id: int, kind: str, ttl: timedelta, now: datetime
) -> tuple[str, Invite]:
    """Create a token for a user, invalidating their earlier unused ones. Returns (raw, row)."""
    revoke_tokens(session, user_id, now)
    raw = new_token()
    row = Invite(
        user_id=user_id,
        kind=kind,
        token_hash=hash_token(raw),
        created_at=now,
        expires_at=now + ttl,
    )
    session.add(row)
    session.flush()
    return raw, row


def _usable(row: Invite | None, now: datetime) -> bool:
    return (
        row is not None and row.used_at is None and row.revoked_at is None and row.expires_at > now
    )


def peek_token(session: Session, token: str, now: datetime) -> Invite | None:
    """The token's row if it is still usable, without using it up."""
    if not token:
        return None
    row = session.scalars(select(Invite).where(Invite.token_hash == hash_token(token))).first()
    return row if _usable(row, now) else None


def consume_token(session: Session, token: str, now: datetime) -> Invite | None:
    """Use a token up exactly once. None when it is unknown, used, revoked or expired."""
    row = peek_token(session, token, now)
    if row is None:
        return None
    # The conditional UPDATE makes "single use" hold even if two requests race for the token.
    result = session.execute(
        update(Invite)
        .where(
            Invite.id == row.id,
            Invite.used_at.is_(None),
            Invite.revoked_at.is_(None),
            Invite.expires_at > now,
        )
        .values(used_at=now)
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        return None
    session.refresh(row)
    return row
