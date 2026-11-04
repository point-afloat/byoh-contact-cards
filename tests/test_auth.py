"""Sign-in throttling at the service level, with exact client addresses and a movable clock.

The HTTP-level behaviour is covered in test_auth_api.py. These tests pin the limits and the
boundaries (login-protection spec: "Throttling keyed by email and client address" and
"Failure accounting").
"""

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.api_errors import ApiError
from app.models import AuthSession, LoginAttempt
from app.services import Services
from tests.auth_helpers import ADMIN_EMAIL, ADMIN_PASSWORD, FakeClock, add_user, running

WRONG = "wrong password here"
HERE = "203.0.113.9"
ELSEWHERE = "198.51.100.7"


def attempt(services: Services, email: str, password: str, ip: str) -> int:
    """The status a sign-in attempt would get: 200, 401 (wrong) or 429 (throttled)."""
    try:
        services.auth.login(email, password, ip)
    except ApiError as exc:
        return exc.status_code
    return 200


def fail(services: Services, email: str, ip: str, times: int) -> None:
    for _ in range(times):
        assert attempt(services, email, WRONG, ip) == 401


def failures(services: Services, *, email: str | None = None, ip: str | None = None) -> int:
    with services.db.session() as db:
        query = select(func.count()).select_from(LoginAttempt)
        if email is not None:
            query = query.where(LoginAttempt.email == email)
        if ip is not None:
            query = query.where(LoginAttempt.ip == ip)
        return db.scalar(query) or 0


def addresses(count: int) -> list[str]:
    return [f"198.51.100.{n}" for n in range(1, count + 1)]


def reach_the_backstop(services: Services, email: str) -> list[str]:
    """Exactly 30 failures for one email from 8 addresses (no address near its own limit).

    Returns the 8 addresses used. A 31st attempt would already be refused.
    """
    ips = addresses(8)
    for ip in ips[:7]:
        fail(services, email, ip, 4)
    fail(services, email, ips[7], 2)
    assert failures(services, email=email) == 30
    return ips


# ---- one person, one place --------------------------------------------------------------------
def test_five_failures_from_one_address_block_that_email_from_that_address(tmp_path: Path) -> None:
    with running(tmp_path) as (_, services):
        fail(services, ADMIN_EMAIL, HERE, 4)
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 200  # four is still fine
        fail(services, ADMIN_EMAIL, HERE, 5)
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 429  # even the right one


def test_a_stranger_cannot_block_the_real_user(tmp_path: Path) -> None:
    with running(tmp_path) as (_, services):
        fail(services, ADMIN_EMAIL, HERE, 5)
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 429
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, ELSEWHERE) == 200


def test_blocking_one_email_at_an_address_leaves_other_emails_there_alone(tmp_path: Path) -> None:
    with running(tmp_path) as (_, services):
        add_user(services, "member@example.org", "a perfectly fine password")
        fail(services, ADMIN_EMAIL, HERE, 5)
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 429
        assert attempt(services, "member@example.org", "a perfectly fine password", HERE) == 200


# ---- many places, one account (the backstop) --------------------------------------------------
def test_guessing_at_one_account_from_many_addresses_stops_at_thirty(tmp_path: Path) -> None:
    ips = addresses(10)
    with running(tmp_path) as (_, services):
        for ip in ips[:7]:
            fail(services, ADMIN_EMAIL, ip, 4)  # 28 failures, no address near its own limit
        fail(services, ADMIN_EMAIL, ips[7], 1)  # 29
        assert failures(services, email=ADMIN_EMAIL) == 29
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, ips[8]) == 200  # 29 is allowed
        fail(services, ADMIN_EMAIL, ips[7], 1)  # 30
        assert failures(services, email=ADMIN_EMAIL) == 30
        # now every address is refused, even a fresh one with the right password
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, ips[9]) == 429


def test_the_backstop_lifts_when_the_window_passes(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock) as (_, services):
        reach_the_backstop(services, ADMIN_EMAIL)
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, "198.51.100.99") == 429
        clock.advance(minutes=10, seconds=1)
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, "198.51.100.99") == 200


# ---- one place, many accounts -----------------------------------------------------------------
def test_one_address_trying_many_emails_is_stopped_at_twenty(tmp_path: Path) -> None:
    with running(tmp_path) as (_, services):
        for n in range(19):
            fail(services, f"user{n}@example.org", HERE, 1)  # 19 failures, one per email
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 200  # 19 is allowed
        fail(services, "user19@example.org", HERE, 1)  # 20
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 429
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, ELSEWHERE) == 200


# ---- how failures are counted -----------------------------------------------------------------
def test_unknown_emails_are_throttled_exactly_like_known_ones(tmp_path: Path) -> None:
    def run(email: str, ip: str, services: Services) -> list[int]:
        return [attempt(services, email, WRONG, ip) for _ in range(5)] + [
            attempt(services, email, WRONG, ip)
        ]

    with running(tmp_path) as (_, services):
        known = run(ADMIN_EMAIL, HERE, services)
        unknown = run("ghost@example.org", ELSEWHERE, services)
    assert known == unknown == [401] * 5 + [429]


def test_unknown_emails_count_towards_the_backstop_too(tmp_path: Path) -> None:
    ghost = "ghost@example.org"
    with running(tmp_path) as (_, services):
        reach_the_backstop(services, ghost)  # an email that has no user
        assert attempt(services, ghost, WRONG, "198.51.100.99") == 429


def test_a_success_clears_only_the_failures_from_that_address(tmp_path: Path) -> None:
    with running(tmp_path) as (_, services):
        fail(services, ADMIN_EMAIL, HERE, 4)
        fail(services, ADMIN_EMAIL, ELSEWHERE, 4)
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 200
        assert failures(services, email=ADMIN_EMAIL, ip=HERE) == 0
        assert failures(services, email=ADMIN_EMAIL, ip=ELSEWHERE) == 4  # still counting


def test_refused_attempts_are_not_recorded_as_failures(tmp_path: Path) -> None:
    with running(tmp_path) as (_, services):
        fail(services, ADMIN_EMAIL, HERE, 5)
        for _ in range(3):
            assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 429
            assert attempt(services, ADMIN_EMAIL, WRONG, HERE) == 429
        assert failures(services, email=ADMIN_EMAIL) == 5


def test_the_pair_limit_lifts_when_the_window_passes(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock) as (_, services):
        fail(services, ADMIN_EMAIL, HERE, 5)
        clock.advance(minutes=9)
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 429
        clock.advance(minutes=1, seconds=1)
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 200


# ---- clean-up of old records ------------------------------------------------------------------
def add_old_failure(services: Services, age: timedelta) -> None:
    """A failed attempt that is `age` old (an address nobody else uses, so it blocks no one)."""
    with services.db.session() as db:
        db.add(
            LoginAttempt(
                email="old@example.org", ip="192.0.2.1", attempted_at=services.clock() - age
            )
        )


def old_failures(services: Services) -> int:
    return failures(services, email="old@example.org")


def add_session(
    services: Services, *, token: str, expires_in: timedelta, last_seen_ago: timedelta
) -> None:
    now: datetime = services.clock()
    with services.db.session() as db:
        user_id = db.scalar(select(func.min(AuthSession.user_id))) or 1
        db.add(
            AuthSession(
                token_hash=token,
                user_id=user_id,
                created_at=now - timedelta(days=1),
                last_seen_at=now - last_seen_ago,
                expires_at=now + expires_in,
            )
        )


def session_tokens(services: Services) -> set[str]:
    with services.db.session() as db:
        return set(db.scalars(select(AuthSession.token_hash)))


def test_failed_attempts_past_the_window_are_removed_and_recent_ones_stay(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock) as (_, services):
        fail(services, ADMIN_EMAIL, HERE, 2)
        clock.advance(minutes=5)
        fail(services, ADMIN_EMAIL, HERE, 1)
        clock.advance(minutes=6)  # the first two are now 11 minutes old, the third 6
        assert failures(services, ip=HERE) == 3
        fail(services, "other@example.org", ELSEWHERE, 1)
        assert failures(services, ip=HERE) == 1


def test_expired_and_idle_sessions_are_removed_and_live_ones_stay(tmp_path: Path) -> None:
    clock = FakeClock()
    day, hour = timedelta(days=1), timedelta(hours=1)
    with running(tmp_path, clock) as (_, services):
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 200  # the first purge
        real = session_tokens(services)
        add_session(services, token="expired", expires_in=-hour, last_seen_ago=hour)
        add_session(services, token="idle", expires_in=day, last_seen_ago=timedelta(hours=13))
        add_session(services, token="live", expires_in=day, last_seen_ago=hour)
        clock.advance(minutes=2)  # the next purge is due
        assert attempt(services, ADMIN_EMAIL, WRONG, HERE) == 401
        assert session_tokens(services) == real | {"live"}


def test_the_purge_runs_at_most_once_a_minute(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock) as (_, services):
        fail(services, ADMIN_EMAIL, HERE, 1)  # first sign-in: the purge runs now
        add_old_failure(services, timedelta(hours=1))
        clock.advance(seconds=59)
        fail(services, ADMIN_EMAIL, HERE, 1)
        assert old_failures(services) == 1  # too soon: left alone
        clock.advance(seconds=2)
        fail(services, ADMIN_EMAIL, HERE, 1)
        assert old_failures(services) == 0


def test_a_refused_sign_in_still_cleans_up(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock) as (_, services):
        fail(services, ADMIN_EMAIL, HERE, 5)
        clock.advance(seconds=61)
        add_old_failure(services, timedelta(hours=1))
        assert attempt(services, ADMIN_EMAIL, ADMIN_PASSWORD, HERE) == 429
        assert old_failures(services) == 0
