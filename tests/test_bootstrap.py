"""Bootstrap of the first administrator (user-authentication spec)."""

import logging
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import User
from tests.auth_helpers import ADMIN_EMAIL, ADMIN_PASSWORD, add_user, running, sign_in, web_client

NOTHING = {"initial_admin_email": None, "initial_admin_password": None}


def users(services) -> list[tuple[str, str]]:  # type: ignore[no-untyped-def]
    with services.db.session() as db:
        return [(u.email, u.role) for u in db.scalars(select(User).order_by(User.id))]


def login_status(client, email: str, password: str) -> int:  # type: ignore[no-untyped-def]
    return int(
        client.post("/api/auth/login", json={"email": email, "password": password}).status_code
    )


# ---- empty database + configuration -> an administrator ---------------------------------------
def test_an_empty_database_gets_an_admin_who_can_sign_in(tmp_path: Path) -> None:
    with running(tmp_path) as (client, services):
        assert users(services) == [(ADMIN_EMAIL, "admin")]
        res = sign_in(client)
        assert res.json()["role"] == "admin"
        assert client.get("/api/auth/me").json() == {"id": 1, "email": ADMIN_EMAIL, "role": "admin"}
        assert client.get("/api/health").status_code == 200


def test_the_configured_email_is_normalised(tmp_path: Path) -> None:
    with running(tmp_path, initial_admin_email="  Admin@Example.ORG ") as (client, services):
        assert users(services) == [("admin@example.org", "admin")]
        assert login_status(client, "ADMIN@example.org", ADMIN_PASSWORD) == 200


def test_the_password_is_stored_hashed_never_in_plain_text(tmp_path: Path) -> None:
    with running(tmp_path) as (_, services):
        with services.db.session() as db:
            stored = db.scalars(select(User.password_hash)).one()
        services.db.engine.dispose()
        assert stored is not None and stored.startswith("$argon2id$")
        assert ADMIN_PASSWORD.encode() not in services.db.path.read_bytes()


def test_bootstrapping_twice_in_one_run_creates_only_one_admin(tmp_path: Path) -> None:
    with running(tmp_path) as (_, services):
        assert services.auth.bootstrap_admin() is False  # startup already created it
        assert len(users(services)) == 1


# ---- existing users: the configuration is ignored ---------------------------------------------
def test_a_restart_with_the_settings_still_present_changes_nothing(tmp_path: Path) -> None:
    with running(tmp_path):
        pass
    with running(
        tmp_path,
        initial_admin_email="someone.else@example.org",
        initial_admin_password="a different long password",
    ) as (client, services):
        assert users(services) == [(ADMIN_EMAIL, "admin")]  # no second account
        assert login_status(client, ADMIN_EMAIL, ADMIN_PASSWORD) == 200  # original unchanged
        assert login_status(client, "someone.else@example.org", "a different long password") == 401


def test_a_changed_password_is_not_reset_by_the_still_configured_one(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        sign_in(client)
        client.post(
            "/api/auth/change-password",
            json={"current_password": ADMIN_PASSWORD, "new_password": "my own new passphrase"},
        )
    with running(tmp_path) as (client, _):  # same configuration as before
        assert login_status(client, ADMIN_EMAIL, ADMIN_PASSWORD) == 401
        assert login_status(client, ADMIN_EMAIL, "my own new passphrase") == 200


def test_any_existing_user_stops_the_bootstrap_even_without_an_admin(tmp_path: Path) -> None:
    with running(tmp_path, **NOTHING) as (_, services):
        add_user(services, "member@example.org")
    with running(tmp_path) as (_, services):  # configuration present now
        assert users(services) == [("member@example.org", "member")]


# ---- nothing configured: a clear error, the health check fails --------------------------------
def test_nothing_configured_is_reported_clearly_and_health_fails(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO), running(tmp_path, **NOTHING) as (client, services):
        health = client.get("/api/health")
        assert users(services) == []
        assert (
            client.post("/api/auth/login", json={"email": "a@b.org", "password": "x"}).status_code
            == 401
        )  # still serving
    assert health.status_code == 503
    problem = " ".join(health.json()["problems"])
    assert "INITIAL_ADMIN_EMAIL" in problem and "INITIAL_ADMIN_PASSWORD" in problem
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("INITIAL_ADMIN_EMAIL" in e for e in errors)


@pytest.mark.parametrize(
    "partial",
    [{"initial_admin_password": None}, {"initial_admin_email": None}],
    ids=["no-password", "no-email"],
)
def test_half_a_configuration_is_just_as_unhealthy(
    tmp_path: Path, partial: dict[str, None]
) -> None:
    with running(tmp_path, **partial) as (client, services):
        assert client.get("/api/health").status_code == 503
        assert users(services) == []


def test_configuring_it_later_and_restarting_fixes_it(tmp_path: Path) -> None:
    with running(tmp_path, **NOTHING) as (client, _):
        assert client.get("/api/health").status_code == 503
    with running(tmp_path) as (client, services):
        assert client.get("/api/health").status_code == 200
        assert users(services) == [(ADMIN_EMAIL, "admin")]


# ---- unusable configuration: reported, nothing created, no secret echoed ----------------------
def test_a_too_short_password_is_refused_without_echoing_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "shortpw1"
    with (
        caplog.at_level(logging.DEBUG),
        running(tmp_path, initial_admin_password=secret) as (client, services),
    ):
        health = client.get("/api/health")
        assert users(services) == []
    assert health.status_code == 503
    assert any(
        "INITIAL_ADMIN_PASSWORD does not meet the password rules" in p
        for p in health.json()["problems"]
    )
    assert secret not in health.text and secret not in caplog.text


def test_a_password_equal_to_the_email_is_refused(tmp_path: Path) -> None:
    with running(tmp_path, initial_admin_password=ADMIN_EMAIL) as (client, services):
        assert client.get("/api/health").status_code == 503
        assert users(services) == []


def test_an_invalid_email_is_refused(tmp_path: Path) -> None:
    with running(tmp_path, initial_admin_email="not-an-email") as (client, services):
        health = client.get("/api/health")
        assert users(services) == []
    assert health.status_code == 503
    assert any("INITIAL_ADMIN_EMAIL is not a valid email" in p for p in health.json()["problems"])


# ---- logging -----------------------------------------------------------------------------------
def test_the_bootstrap_logs_a_generic_line_with_no_credentials(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG), running(tmp_path):
        pass
    assert "Created the first administrator account" in caplog.text
    assert ADMIN_PASSWORD not in caplog.text and ADMIN_EMAIL not in caplog.text


def test_a_second_browser_is_independent_after_bootstrap(tmp_path: Path) -> None:
    with running(tmp_path) as (_, services):
        other = web_client(services)
        assert login_status(other, ADMIN_EMAIL, ADMIN_PASSWORD) == 200
