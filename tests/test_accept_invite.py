"""Accepting an invitation or a reset link (user-administration spec)."""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import TOKEN_INVITE, TOKEN_RESET, User
from app.services import Services
from app.tokens import issue_token
from tests.auth_helpers import ADMIN_EMAIL, FakeClock, add_user, running, sign_in, web_client

Env = tuple[TestClient, Services, FakeClock]
PASSWORD = "the invitee's chosen passphrase"
INVALID = {
    "code": "invite_invalid",
    "message": "This link is no longer valid. Ask an administrator for a new one.",
}


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    clock = FakeClock()
    with running(tmp_path, clock) as (client, services):
        sign_in(client)
        yield client, services, clock


def invite(
    client: TestClient, email: str = "new@example.org", role: str = "member"
) -> dict[str, Any]:
    result: dict[str, Any] = client.post(
        "/api/admin/users", json={"email": email, "role": role}
    ).json()
    return result


def accept(
    services: Services, token: str, password: str = PASSWORD
) -> tuple[TestClient, httpx.Response]:
    visitor = web_client(services)  # nobody is signed in
    return visitor, visitor.post(
        "/api/auth/accept-invite", json={"token": token, "password": password}
    )


def issue(services: Services, clock: FakeClock, user_id: int, kind: str, ttl: timedelta) -> str:
    with services.db.session() as db:
        return issue_token(db, user_id, kind, ttl, clock.now)[0]


# ---- a valid invitation ---------------------------------------------------------------------
def test_accepting_activates_the_account_and_signs_the_person_in(env: Env) -> None:
    client, services, _ = env
    token = invite(client, "new@example.org", "admin")["token"]
    visitor, res = accept(services, token)
    assert res.status_code == 200
    assert res.json() == {"id": 2, "email": "new@example.org", "role": "admin"}
    assert "httponly" in res.headers["set-cookie"].lower()
    assert visitor.get("/api/auth/me").json()["email"] == "new@example.org"
    listed = {u["email"]: u for u in client.get("/api/admin/users").json()}
    assert listed["new@example.org"]["status"] == "active"
    assert listed["new@example.org"]["invite_expires_at"] is None
    assert listed["new@example.org"]["last_sign_in_at"] is not None


def test_the_new_password_works_for_later_sign_ins(env: Env) -> None:
    client, services, _ = env
    accept(services, invite(client)["token"])
    again = web_client(services)
    res = again.post("/api/auth/login", json={"email": "new@example.org", "password": PASSWORD})
    assert res.status_code == 200


def test_the_password_is_stored_hashed(env: Env) -> None:
    client, services, _ = env
    accept(services, invite(client)["token"])
    services.db.engine.dispose()
    assert PASSWORD.encode() not in services.db.path.read_bytes()


def test_the_invite_page_can_check_a_link_without_using_it_up(env: Env) -> None:
    client, services, _ = env
    token = invite(client, "new@example.org")["token"]
    page = web_client(services)
    for _ in range(2):
        res = page.post("/api/auth/invite-info", json={"token": token})
        assert res.status_code == 200 and res.json() == {
            "email": "new@example.org",
            "kind": "invite",
        }
    assert accept(services, token)[1].status_code == 200


# ---- links that no longer work --------------------------------------------------------------
def test_a_link_works_exactly_once(env: Env) -> None:
    client, services, _ = env
    token = invite(client)["token"]
    assert accept(services, token)[1].status_code == 200
    _, second = accept(services, token, "another long passphrase here")
    assert second.status_code == 400 and second.json() == INVALID
    info = web_client(services).post("/api/auth/invite-info", json={"token": token})
    assert info.status_code == 400 and info.json() == INVALID


def test_an_expired_link_is_refused_and_says_to_ask_an_admin(env: Env) -> None:
    client, services, clock = env
    token = invite(client)["token"]
    clock.advance(days=7, minutes=1)
    for res in (
        web_client(services).post("/api/auth/invite-info", json={"token": token}),
        accept(services, token)[1],
    ):
        assert res.status_code == 400 and res.json() == INVALID
        assert "administrator" in res.json()["message"]


def test_unknown_links_are_refused_with_the_same_answer(env: Env) -> None:
    _, services, _ = env
    for token in ("", "nope", "a" * 43):
        assert (
            web_client(services).post("/api/auth/invite-info", json={"token": token}).json()
            == INVALID
        )
        assert accept(services, token)[1].json() == INVALID


def test_a_reissued_link_replaces_the_old_one(env: Env) -> None:
    client, services, _ = env
    first = invite(client)
    second = client.post(f"/api/admin/users/{first['user']['id']}/invite").json()
    assert accept(services, first["token"])[1].json() == INVALID
    assert accept(services, second["token"])[1].status_code == 200


def test_a_revoked_invitation_cannot_be_accepted(env: Env) -> None:
    client, services, _ = env
    first = invite(client)
    client.delete(f"/api/admin/users/{first['user']['id']}/invite")
    assert accept(services, first["token"])[1].json() == INVALID


def test_an_invitation_for_a_deactivated_user_is_refused(env: Env) -> None:
    client, services, _ = env
    first = invite(client)
    with services.db.session() as db:
        db.scalars(select(User).where(User.email == "new@example.org")).one().is_active = False
    assert accept(services, first["token"])[1].json() == INVALID


def test_an_invitation_cannot_be_used_on_an_account_that_already_has_a_password(env: Env) -> None:
    _, services, clock = env
    member_id = add_user(services, "member@example.org", "member's long password")
    token = issue(services, clock, member_id, TOKEN_INVITE, timedelta(days=1))
    assert accept(services, token, "hijack attempt passphrase")[1].json() == INVALID
    assert (
        web_client(services)
        .post(
            "/api/auth/login",
            json={"email": "member@example.org", "password": "member's long password"},
        )
        .status_code
        == 200
    )  # the original password still works


# ---- password rules -------------------------------------------------------------------------
def test_a_weak_password_is_a_field_error_and_does_not_burn_the_link(env: Env) -> None:
    client, services, _ = env
    token = invite(client)["token"]
    for weak in ("short", "password1234"):
        _, res = accept(services, token, weak)
        assert res.status_code == 422 and "password" in res.json()["errors"]
    assert accept(services, token)[1].status_code == 200


def test_the_password_may_not_be_the_email_address(env: Env) -> None:
    client, services, _ = env
    token = invite(client, "new.person@example.org")["token"]
    assert accept(services, token, "new.person@example.org")[1].status_code == 422


# ---- reset links (issued by an admin in 3.3, accepted here) ---------------------------------
def test_a_reset_link_changes_the_password_and_signs_out_other_sessions(env: Env) -> None:
    _, services, clock = env
    member_id = add_user(services, "member@example.org", "member's old long password")
    old_session = web_client(services)
    sign_in(old_session, "member@example.org", "member's old long password")
    token = issue(services, clock, member_id, TOKEN_RESET, timedelta(hours=1))

    info = web_client(services).post("/api/auth/invite-info", json={"token": token})
    assert info.json() == {"email": "member@example.org", "kind": "reset"}
    fresh, res = accept(services, token, "member's brand new password")
    assert res.status_code == 200
    assert fresh.get("/api/auth/me").status_code == 200  # signed in with the new password
    assert old_session.get("/api/auth/me").status_code == 401  # everywhere else: signed out
    assert (
        web_client(services)
        .post(
            "/api/auth/login",
            json={"email": "member@example.org", "password": "member's old long password"},
        )
        .status_code
        == 401
    )
    assert accept(services, token, "yet another long password")[1].json() == INVALID


def test_a_reset_link_is_refused_for_a_pending_account(env: Env) -> None:
    client, services, clock = env
    pending = invite(client)["user"]["id"]
    token = issue(services, clock, pending, TOKEN_RESET, timedelta(hours=1))
    assert accept(services, token)[1].json() == INVALID


def test_the_admin_account_is_unaffected_by_other_peoples_invitations(env: Env) -> None:
    client, services, _ = env
    accept(services, invite(client)["token"])
    assert client.get("/api/auth/me").json()["email"] == ADMIN_EMAIL
