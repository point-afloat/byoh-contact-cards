"""Sign-in, sessions, sign-out, password change, throttling (user-authentication spec)."""

import re
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import AuthSession, LoginAttempt, User
from tests.auth_helpers import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    FakeClock,
    add_user,
    running,
    sign_in,
    web_client,
)

NEW_PASSWORD = "an entirely new passphrase"


def login(client, email: str, password: str, **headers: str):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/auth/login", json={"email": email, "password": password}, headers=headers
    )


# ---- 2.1 sign in / out and sessions ---------------------------------------------------------
def test_valid_credentials_sign_in_and_set_a_hardened_cookie(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        res = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert res.status_code == 200
        assert res.json() == {"id": 1, "email": ADMIN_EMAIL, "role": "admin"}
        cookie = res.headers["set-cookie"].lower()
        assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
        assert "path=/" in cookie and f"max-age={14 * 86400}" in cookie
        assert client.get("/api/auth/me").json()["email"] == ADMIN_EMAIL


def test_the_session_cookie_is_never_stored_in_plain_text(tmp_path: Path) -> None:
    with running(tmp_path) as (client, services):
        raw = re.search(
            r"session=([^;]+)", login(client, ADMIN_EMAIL, ADMIN_PASSWORD).headers["set-cookie"]
        )
        assert raw is not None
        services.db.engine.dispose()
        assert raw.group(1).encode() not in services.db.path.read_bytes()
        with services.db.session() as db:
            assert db.scalars(select(AuthSession.token_hash)).one() != raw.group(1)


def test_wrong_password_and_unknown_email_give_the_same_answer(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        wrong = login(client, ADMIN_EMAIL, "definitely not the password")
        unknown = login(client, "nobody@example.org", "definitely not the password")
    assert wrong.status_code == unknown.status_code == 401
    assert (
        wrong.json()
        == unknown.json()
        == {
            "code": "invalid_credentials",
            "message": "Email or password incorrect.",
        }
    )


def test_deactivated_and_pending_users_cannot_sign_in_with_the_generic_message(
    tmp_path: Path,
) -> None:
    with running(tmp_path) as (client, services):
        add_user(services, "off@example.org", "a perfectly fine password", active=False)
        add_user(services, "pending@example.org", password=None)
        for email, password in [
            ("off@example.org", "a perfectly fine password"),
            ("pending@example.org", ""),
        ]:
            res = login(client, email, password)
            assert res.status_code == 401 and res.json()["code"] == "invalid_credentials"


def test_email_is_case_insensitive_and_trimmed(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        assert login(client, f"  {ADMIN_EMAIL.upper()} ", ADMIN_PASSWORD).status_code == 200


def test_signing_in_records_the_last_sign_in(tmp_path: Path) -> None:
    with running(tmp_path) as (client, services):
        sign_in(client)
        with services.db.session() as db:
            assert db.scalars(select(User.last_sign_in_at)).one() is not None


def test_logout_ends_the_session_and_clears_the_cookie(tmp_path: Path) -> None:
    with running(tmp_path) as (client, services):
        sign_in(client)
        res = client.post("/api/auth/logout")
        assert res.status_code == 200
        assert (
            'session=""' in res.headers["set-cookie"]
            or "max-age=0" in res.headers["set-cookie"].lower()
        )
        with services.db.session() as db:
            assert db.scalars(select(AuthSession)).all() == []
        # even a client that kept the old cookie is signed out
        assert client.get("/api/auth/me").status_code == 401


def test_me_without_a_session_is_a_401_with_no_data(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.json() == {"code": "not_authenticated", "message": "Please sign in."}


def test_an_idle_session_expires_but_activity_keeps_it_alive(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock) as (client, _):
        sign_in(client)
        clock.advance(hours=11)
        assert client.get("/api/auth/me").status_code == 200
        clock.advance(hours=11)  # 22 h after sign-in, but only 11 h idle
        assert client.get("/api/auth/me").status_code == 200
        clock.advance(hours=13)  # idle for more than 12 h
        assert client.get("/api/auth/me").status_code == 401


def test_a_session_has_an_absolute_lifetime_however_active_the_user_is(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock) as (client, _):
        sign_in(client)
        for _ in range(30):  # 30 * 11 h = 13.75 days, always active
            clock.advance(hours=11)
            assert client.get("/api/auth/me").status_code == 200
        clock.advance(hours=11)  # past 14 days
        assert client.get("/api/auth/me").status_code == 401


def test_deactivating_a_user_ends_their_session_on_the_next_request(tmp_path: Path) -> None:
    with running(tmp_path) as (client, services):
        add_user(services, "member@example.org", "a perfectly fine password")
        sign_in(client, "member@example.org", "a perfectly fine password")
        assert client.get("/api/auth/me").status_code == 200
        with services.db.session() as db:
            db.scalars(
                select(User).where(User.email == "member@example.org")
            ).one().is_active = False
        assert client.get("/api/auth/me").status_code == 401


# ---- 2.2 change own password ----------------------------------------------------------------
def test_changing_the_password_ends_other_sessions_but_keeps_this_one(tmp_path: Path) -> None:
    with running(tmp_path) as (here, services):
        sign_in(here)
        elsewhere = web_client(services)
        sign_in(elsewhere)
        res = here.post(
            "/api/auth/change-password",
            json={"current_password": ADMIN_PASSWORD, "new_password": NEW_PASSWORD},
        )
        assert res.status_code == 200
        assert here.get("/api/auth/me").status_code == 200
        assert elsewhere.get("/api/auth/me").status_code == 401
        assert login(web_client(services), ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 401
        assert login(web_client(services), ADMIN_EMAIL, NEW_PASSWORD).status_code == 200


def test_a_wrong_current_password_changes_nothing(tmp_path: Path) -> None:
    with running(tmp_path) as (client, services):
        sign_in(client)
        res = client.post(
            "/api/auth/change-password",
            json={"current_password": "not my password", "new_password": NEW_PASSWORD},
        )
        assert res.status_code == 400 and res.json()["code"] == "wrong_password"
        assert "current_password" in res.json()["errors"]
        assert login(web_client(services), ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200


def test_a_weak_new_password_is_rejected_with_a_field_error(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        sign_in(client)
        res = client.post(
            "/api/auth/change-password",
            json={"current_password": ADMIN_PASSWORD, "new_password": "short"},
        )
    assert res.status_code == 422 and "12" in res.json()["errors"]["new_password"]


def test_changing_the_password_needs_a_session(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        res = client.post(
            "/api/auth/change-password",
            json={"current_password": ADMIN_PASSWORD, "new_password": NEW_PASSWORD},
        )
    assert res.status_code == 401


def test_guessing_the_current_password_is_throttled(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        sign_in(client)
        body = {"current_password": "wrong guess here", "new_password": NEW_PASSWORD}
        codes = [client.post("/api/auth/change-password", json=body).status_code for _ in range(6)]
        right = client.post(
            "/api/auth/change-password",
            json={"current_password": ADMIN_PASSWORD, "new_password": NEW_PASSWORD},
        )
    assert codes == [400] * 5 + [429]
    assert right.status_code == 429


# ---- 2.3 login throttling -------------------------------------------------------------------
def test_five_failures_block_even_the_correct_password(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        for _ in range(5):
            assert login(client, ADMIN_EMAIL, "wrong password here").status_code == 401
        blocked = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert blocked.status_code == 429
    assert blocked.json() == {
        "code": "too_many_attempts",
        "message": "Too many failed attempts. Please try again later.",
    }


def test_the_block_lifts_after_the_window(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock) as (client, _):
        for _ in range(5):
            login(client, ADMIN_EMAIL, "wrong password here")
        assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 429
        clock.advance(minutes=10, seconds=1)
        assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200


def test_refused_attempts_do_not_extend_the_block(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock) as (client, _):
        for _ in range(5):
            login(client, ADMIN_EMAIL, "wrong password here")
        clock.advance(minutes=9)
        for _ in range(6):  # refused, and must not count as new failures
            assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 429
        clock.advance(minutes=1, seconds=1)
        assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200


def test_unknown_emails_are_throttled_exactly_like_known_ones(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        codes = [
            login(client, "ghost@example.org", "wrong password here").status_code for _ in range(6)
        ]
    assert codes == [401] * 5 + [429]


def test_a_successful_sign_in_clears_earlier_failures(tmp_path: Path) -> None:
    with running(tmp_path) as (client, services):
        for _ in range(4):
            login(client, ADMIN_EMAIL, "wrong password here")
        assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200
        other = web_client(services)
        for _ in range(4):
            assert login(other, ADMIN_EMAIL, "wrong password here").status_code == 401
        assert login(other, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200  # 4 + 4 never added up


def test_one_address_guessing_many_accounts_is_blocked(tmp_path: Path) -> None:
    with running(tmp_path, trusted_proxy=True) as (client, _):
        attacker = {"X-Forwarded-For": "203.0.113.9"}
        for i in range(20):
            assert (
                login(client, f"user{i}@example.org", "wrong password here", **attacker).status_code
                == 401
            )
        assert (
            login(client, "fresh@example.org", "wrong password here", **attacker).status_code == 429
        )
        # a different address is unaffected
        elsewhere = {"X-Forwarded-For": "198.51.100.7"}
        assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD, **elsewhere).status_code == 200


def test_a_stranger_guessing_cannot_lock_the_real_user_out(tmp_path: Path) -> None:
    with running(tmp_path, trusted_proxy=True) as (client, _):
        stranger = {"X-Forwarded-For": "203.0.113.9"}
        for _ in range(5):
            assert login(client, ADMIN_EMAIL, "wrong password here", **stranger).status_code == 401
        assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD, **stranger).status_code == 429
        owner = {"X-Forwarded-For": "198.51.100.7"}  # the real user, from somewhere else
        assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD, **owner).status_code == 200


def test_forwarded_addresses_are_ignored_unless_a_proxy_is_trusted(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):  # trusted_proxy is off by default
        for i in range(20):
            login(
                client,
                f"user{i}@example.org",
                "wrong password here",
                **{"X-Forwarded-For": f"10.0.0.{i}"},
            )
        # spoofing a new address each time did not help: all 20 count against the real one
        res = login(
            client, "fresh@example.org", "wrong password here", **{"X-Forwarded-For": "1.1.1.1"}
        )
    assert res.status_code == 429


def test_the_last_forwarded_address_is_used_because_the_client_cannot_forge_it(
    tmp_path: Path,
) -> None:
    with running(tmp_path, trusted_proxy=True) as (client, _):
        for i in range(20):  # the client prepends fake addresses, the proxy appends the real one
            login(
                client,
                f"user{i}@example.org",
                "wrong password here",
                **{"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"},
            )
        res = login(
            client,
            "fresh@example.org",
            "wrong password here",
            **{"X-Forwarded-For": "1.2.3.4, 203.0.113.9"},
        )
    assert res.status_code == 429


# ---- limits on sign-in input ------------------------------------------------------------------
def attempt_rows(services) -> int:  # type: ignore[no-untyped-def]
    with services.db.session() as db:
        return db.scalar(select(func.count()).select_from(LoginAttempt)) or 0


def test_an_oversized_email_is_a_validation_error_and_leaves_no_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hashed: list[str] = []
    monkeypatch.setattr("app.auth.verify_password", lambda *a: hashed.append("x") or False)
    with running(tmp_path) as (client, services):
        res = login(client, "a" * 309 + "@example.org", "wrong password here")  # 321 characters
        assert res.status_code == 422 and res.json()["code"] == "validation_error"
        assert attempt_rows(services) == 0
    assert hashed == []


def test_an_oversized_password_is_a_validation_error_and_is_never_hashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hashed: list[str] = []
    monkeypatch.setattr("app.auth.verify_password", lambda *a: hashed.append("x") or False)
    with running(tmp_path) as (client, services):
        res = login(client, ADMIN_EMAIL, "p" * 1025)
        assert res.status_code == 422 and res.json()["code"] == "validation_error"
        assert attempt_rows(services) == 0
    assert hashed == []


def test_oversized_attempts_do_not_count_towards_a_lockout(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        for _ in range(10):
            assert login(client, ADMIN_EMAIL, "p" * 1025).status_code == 422
        assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200


def test_input_exactly_at_the_limits_is_still_checked_normally(tmp_path: Path) -> None:
    long_email = "a" * 308 + "@example.org"  # exactly 320 characters
    with running(tmp_path) as (client, services):
        assert login(client, long_email, "p" * 1024).status_code == 401
        assert attempt_rows(services) == 1
