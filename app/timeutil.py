"""One notion of time for the app: naive UTC datetimes (what SQLite stores), injectable in tests."""

from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
