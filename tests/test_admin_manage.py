"""Deactivate, reactivate, roles, reset links and last-admin protection (user-administration)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import AuthSession, User
from app.services import Services
from tests.auth_helpers import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    FakeClock,
    add_user,
    running,
    sign_in,
    web_client,
)

Env = tuple[TestClient, Services, FakeClock]
MEMBER = "member@example.org"
MEMBER_PASSWORD = "the member's long password"
NEW_PASSWORD = "a brand new long password"


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    clock = FakeClock()
    with running(tmp_path, clock) as (client, services):
        sign_in(client)
        yield client, services, clock


def user_id(services: Services, email: str) -> int:
    with services.db.session() as db:
        return db.scalars(select(User.id).where(User.email == email)).one()


def patch(client: TestClient, uid: int, **body: Any) -> Any:
    return client.patch(f"/api/admin/users/{uid}", json=body)


def member_session(services: Services) -> tuple[int, TestClient]:
    uid = add_user(services, MEMBER, MEMBER_PASSWORD)
    browser = web_client(services)
    sign_in(browser, MEMBER, MEMBER_PASSWORD)
    return uid, browser


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---- deactivate / reactivate ----------------------------------------------------------------
def test_deactivating_signs_the_user_out_on_their_next_request(env: Env) -> None:
    client, services, _ = env
    uid, browser = member_session(services)
    assert browser.get("/api/auth/me").status_code == 200

    res = patch(client, uid, is_active=False)
    assert res.status_code == 200 and res.json()["status"] == "inactive"
    assert browser.get("/api/auth/me").status_code == 401  # signed out at once
    with services.db.session() as db:
        assert db.scalars(select(AuthSession).where(AuthSession.user_id == uid)).all() == []
    refused = web_client(services).post(
        "/api/auth/login", json={"email": MEMBER, "password": MEMBER_PASSWORD}
    )
    assert refused.status_code == 401 and refused.json()["code"] == "invalid_credentials"
    listed = {u["email"]: u for u in client.get("/api/admin/users").json()}
    assert listed[MEMBER]["status"] == "inactive"


def test_reactivating_restores_access_with_the_old_password(env: Env) -> None:
    client, services, _ = env
    uid, _ = member_session(services)
    patch(client, uid, is_active=False)
    res = patch(client, uid, is_active=True)
    assert res.json()["status"] == "active"
    again = web_client(services).post(
        "/api/auth/login", json={"email": MEMBER, "password": MEMBER_PASSWORD}
    )
    assert again.status_code == 200  # no reset needed, nothing lost


def test_a_pending_invitation_cannot_be_deactivated(env: Env) -> None:
    client, services, _ = env
    pending = client.post(
        "/api/admin/users", json={"email": "p@example.org", "role": "member"}
    ).json()
    res = patch(client, pending["user"]["id"], is_active=False)
    assert res.status_code == 409 and res.json()["code"] == "user_pending"
    assert user_id(services, "p@example.org") == pending["user"]["id"]


def test_unknown_users_and_empty_or_invalid_changes_are_refused(env: Env) -> None:
    client, services, _ = env
    uid, _ = member_session(services)
    assert patch(client, 999, is_active=False).json()["code"] == "user_not_found"
    assert patch(client, uid).status_code == 422  # nothing to change
    bad = patch(client, uid, role="superuser")
    assert bad.status_code == 422 and "role" in bad.json()["errors"]


# ---- roles ----------------------------------------------------------------------------------
def test_promoting_a_member_gives_access_on_their_next_request(env: Env) -> None:
    client, services, _ = env
    uid, browser = member_session(services)
    assert browser.get("/api/admin/users").status_code == 403
    assert patch(client, uid, role="admin").json()["role"] == "admin"
    assert browser.get("/api/admin/users").status_code == 200  # same session, new role


def test_demoting_an_admin_takes_the_access_away_immediately(env: Env) -> None:
    client, services, _ = env
    uid = add_user(services, "second@example.org", MEMBER_PASSWORD, role="admin")
    second = web_client(services)
    sign_in(second, "second@example.org", MEMBER_PASSWORD)
    assert second.get("/api/admin/users").status_code == 200
    assert patch(client, uid, role="member").status_code == 200
    assert second.get("/api/admin/users").status_code == 403


def test_a_pending_users_role_can_be_changed_before_they_accept(env: Env) -> None:
    client, _, _ = env
    pending = client.post(
        "/api/admin/users", json={"email": "p@example.org", "role": "member"}
    ).json()
    assert patch(client, pending["user"]["id"], role="admin").json()["role"] == "admin"


# ---- the last administrator -----------------------------------------------------------------
def test_the_only_admin_cannot_deactivate_or_demote_themselves(env: Env) -> None:
    client, services, _ = env
    me = user_id(services, ADMIN_EMAIL)
    for change in (
        {"is_active": False},
        {"role": "member"},
        {"role": "member", "is_active": False},
    ):
        res = patch(client, me, **change)
        assert res.status_code == 409 and res.json()["code"] == "last_admin"
        assert "administrator" in res.json()["message"]
    assert client.get("/api/auth/me").json()["role"] == "admin"  # still signed in, still admin


def test_an_inactive_admin_does_not_count_as_a_spare(env: Env) -> None:
    client, services, _ = env
    add_user(services, "off@example.org", MEMBER_PASSWORD, role="admin", active=False)
    assert patch(client, user_id(services, ADMIN_EMAIL), is_active=False).status_code == 409


def test_a_pending_admin_does_not_count_as_a_spare(env: Env) -> None:
    client, services, _ = env
    client.post("/api/admin/users", json={"email": "p@example.org", "role": "admin"})
    assert patch(client, user_id(services, ADMIN_EMAIL), role="member").status_code == 409


def test_with_a_second_active_admin_anyone_may_step_down(env: Env) -> None:
    client, services, _ = env
    second_id = add_user(services, "second@example.org", MEMBER_PASSWORD, role="admin")
    me = user_id(services, ADMIN_EMAIL)
    assert patch(client, me, role="member").status_code == 200  # the first admin steps down
    second = web_client(services)
    sign_in(second, "second@example.org", MEMBER_PASSWORD)
    # now the second one is the last
    res = patch(second, second_id, is_active=False)
    assert res.status_code == 409 and res.json()["code"] == "last_admin"


def test_deactivating_another_admin_is_fine_while_one_remains(env: Env) -> None:
    client, services, _ = env
    second_id = add_user(services, "second@example.org", MEMBER_PASSWORD, role="admin")
    assert patch(client, second_id, is_active=False).status_code == 200
    # but the remaining one is now protected
    assert patch(client, user_id(services, ADMIN_EMAIL), is_active=False).status_code == 409


def test_only_admins_may_change_users(env: Env) -> None:
    client, services, _ = env
    uid, browser = member_session(services)
    assert patch(browser, uid, role="admin").status_code == 403
    assert browser.post(f"/api/admin/users/{uid}/reset-link").status_code == 403
    assert client.get("/api/admin/users").json()[1]["role"] == "member"  # unchanged


# ---- reset links ----------------------------------------------------------------------------
def test_an_admin_can_issue_a_reset_link_that_expires(env: Env) -> None:
    client, services, clock = env
    uid, _ = member_session(services)
    res = client.post(f"/api/admin/users/{uid}/reset-link")
    assert res.status_code == 200
    body = res.json()
    assert (
        len(body["token"]) >= 43 and body["invite_path"] == f"/accept-invite#token={body['token']}"
    )
    assert parse(body["expires_at"]) == clock.now.replace(tzinfo=UTC) + timedelta(minutes=60)
    info = web_client(services).post("/api/auth/invite-info", json={"token": body["token"]})
    assert info.json() == {"email": MEMBER, "kind": "reset"}
    clock.advance(minutes=61)
    expired = web_client(services).post("/api/auth/invite-info", json={"token": body["token"]})
    assert expired.status_code == 400 and expired.json()["code"] == "invite_invalid"


def test_the_reset_lifetime_is_configurable(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock, auth_reset_ttl_minutes=5) as (client, services):
        sign_in(client)
        uid = add_user(services, MEMBER, MEMBER_PASSWORD)
        body = client.post(f"/api/admin/users/{uid}/reset-link").json()
    assert parse(body["expires_at"]) == clock.now.replace(tzinfo=UTC) + timedelta(minutes=5)


def test_using_the_reset_link_replaces_the_password_and_ends_other_sessions(env: Env) -> None:
    client, services, _ = env
    uid, old_browser = member_session(services)
    token = client.post(f"/api/admin/users/{uid}/reset-link").json()["token"]
    # issuing the link changes nothing yet: the old password and session still work
    assert old_browser.get("/api/auth/me").status_code == 200
    assert (
        web_client(services)
        .post("/api/auth/login", json={"email": MEMBER, "password": MEMBER_PASSWORD})
        .status_code
        == 200
    )

    fresh = web_client(services)
    res = fresh.post("/api/auth/accept-invite", json={"token": token, "password": NEW_PASSWORD})
    assert res.status_code == 200
    assert old_browser.get("/api/auth/me").status_code == 401
    assert (
        web_client(services)
        .post("/api/auth/login", json={"email": MEMBER, "password": MEMBER_PASSWORD})
        .status_code
        == 401
    )
    assert fresh.get("/api/auth/me").status_code == 200


def test_a_new_reset_link_replaces_the_previous_one(env: Env) -> None:
    client, services, _ = env
    uid, _ = member_session(services)
    first = client.post(f"/api/admin/users/{uid}/reset-link").json()["token"]
    second = client.post(f"/api/admin/users/{uid}/reset-link").json()["token"]
    page = web_client(services)
    assert page.post("/api/auth/invite-info", json={"token": first}).status_code == 400
    assert page.post("/api/auth/invite-info", json={"token": second}).status_code == 200


def test_reset_links_need_an_active_user_with_a_password(env: Env) -> None:
    client, services, _ = env
    pending = client.post(
        "/api/admin/users", json={"email": "p@example.org", "role": "member"}
    ).json()
    off = add_user(services, "off@example.org", MEMBER_PASSWORD, active=False)
    assert (
        client.post(f"/api/admin/users/{pending['user']['id']}/reset-link").json()["code"]
        == "user_pending"
    )
    assert client.post(f"/api/admin/users/{off}/reset-link").json()["code"] == "user_inactive"
    assert client.post("/api/admin/users/999/reset-link").json()["code"] == "user_not_found"


def test_an_admin_can_reset_their_own_password_too(env: Env) -> None:
    client, services, _ = env
    token = client.post(f"/api/admin/users/{user_id(services, ADMIN_EMAIL)}/reset-link").json()[
        "token"
    ]
    res = web_client(services).post(
        "/api/auth/accept-invite", json={"token": token, "password": NEW_PASSWORD}
    )
    assert res.status_code == 200
    assert client.get("/api/auth/me").status_code == 401  # the old admin session ended
    assert (
        web_client(services)
        .post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        .status_code
        == 401
    )


def test_the_raw_reset_token_is_never_stored(env: Env) -> None:
    client, services, _ = env
    uid, _ = member_session(services)
    token = client.post(f"/api/admin/users/{uid}/reset-link").json()["token"]
    services.db.engine.dispose()
    assert token.encode() not in services.db.path.read_bytes()
