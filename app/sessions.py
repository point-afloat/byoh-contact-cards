"""In-memory review sessions.

Card images and extracted contacts live only here, keyed by an unguessable id, and
are discarded on send or after the inactivity timeout. Nothing is written to disk
or logs. This assumes a single worker process.
"""

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.api_errors import ApiError
from app.contact import Contact
from app.images import PreparedImage

SESSION_EXPIRED = ApiError(
    404, "session_expired", "This review session has expired. Please scan the card again."
)


def session_expired() -> ApiError:
    return ApiError(SESSION_EXPIRED.status_code, SESSION_EXPIRED.code, SESSION_EXPIRED.message)


@dataclass
class Session:
    id: str
    image: PreparedImage | None = field(repr=False)
    contact: Contact | None = field(repr=False)
    notice: str | None
    expires_at: float
    sent: bool = False
    person_id: str | None = None
    record_type: str | None = None  # "person" or "company", once sent
    created_company: tuple[str, int] | None = None  # (name, id) created by an earlier attempt
    send_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class SessionStore:
    def __init__(
        self,
        ttl_seconds: int,
        max_sessions: int = 200,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._clock = clock
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, image: PreparedImage, contact: Contact, notice: str | None = None) -> Session:
        with self._lock:
            self._purge()
            if len(self._sessions) >= self._max:
                raise ApiError(
                    503, "too_many_sessions", "The server is busy. Please try again shortly."
                )
            session = Session(
                id=secrets.token_urlsafe(32),
                image=image,
                contact=contact,
                notice=notice,
                expires_at=self._clock() + self._ttl,
            )
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str) -> Session:
        """Return the live session and extend its lifetime, or raise session_expired."""
        with self._lock:
            self._purge()
            session = self._sessions.get(session_id)
            if session is None:
                raise session_expired()
            session.expires_at = self._clock() + self._ttl
            return session

    def update_contact(self, session_id: str, contact: Contact) -> Session:
        session = self.get(session_id)
        with self._lock:
            if session.sent:
                raise ApiError(409, "already_sent", "This contact was already sent.")
            session.contact = contact
        return session

    def mark_sent(
        self, session_id: str, person_id: str | None, record_type: str = "person"
    ) -> Session:
        """Record a successful send and discard the card image and contact data."""
        session = self.get(session_id)
        with self._lock:
            session.sent = True
            session.person_id = person_id
            session.record_type = record_type
            session.image = None
            session.contact = None
        return session

    def discard(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def __len__(self) -> int:
        with self._lock:
            self._purge()
            return len(self._sessions)

    def _purge(self) -> None:
        now = self._clock()
        for key in [k for k, s in self._sessions.items() if s.expires_at <= now]:
            del self._sessions[key]
