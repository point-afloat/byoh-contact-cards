"""Admin user management: list, invite, re-issue, revoke (user-administration spec)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import TOKEN_INVITE, User
from app.services import Services
from app.tokens import peek_token
from tests.auth_helpers import (
    ADMIN_EMAIL,
    FakeClock,
    add_user,
    running,
    sign_in,
    web_client,
)

Env = tuple[TestClient, Services, FakeClock]
MEMBER_PASSWORD = "a member's long password"


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    clock = FakeClock()
    with running(tmp_path, clock) as (client, services):
        sign_in(client)  # the bootstrap administrator
        yield client, services, clock


def utc(naive: datetime) -> datetime:
    return naive.replace(tzinfo=UTC)


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def usable(services: Services, clock: FakeClock, token: str) -> bool:
    with services.db.session() as db:
        return peek_token(db, token, clock.now) is not None


def user_emails(services: Services) -> list[str]:
    with services.db.session() as db:
        return list(db.scalars(select(User.email).order_by(User.id)))


# ---- only administrators --------------------------------------------------------------------
def test_members_are_refused_everywhere_and_see_no_data(env: Env) -> None:
    client, services, _ = env
    add_user(services, "member@example.org", MEMBER_PASSWORD)
    pending_id = client.post(
        "/api/admin/users", json={"email": "p@example.org", "role": "member"}
    ).json()["user"]["id"]
    member = web_client(services)
    sign_in(member, "member@example.org", MEMBER_PASSWORD)
    before = user_emails(services)

    responses = [
        member.get("/api/admin/users"),
        member.post("/api/admin/users", json={"email": "new@example.org", "role": "member"}),
        member.post(f"/api/admin/users/{pending_id}/invite"),
        member.delete(f"/api/admin/users/{pending_id}/invite"),
    ]
    for response in responses:
        assert response.status_code == 403
        assert response.json() == {
            "code": "forbidden",
            "message": "Only administrators can do this.",
        }
    assert user_emails(services) == before  # nothing changed


def test_anonymous_callers_get_401_on_the_admin_routes(env: Env) -> None:
    _, services, _ = env
    anonymous = web_client(services)
    assert anonymous.get("/api/admin/users").status_code == 401
    assert (
        anonymous.post("/api/admin/users", json={"email": "x@y.org", "role": "member"}).status_code
        == 401
    )


# ---- listing --------------------------------------------------------------------------------
def test_the_list_shows_every_user_with_role_status_and_last_sign_in(env: Env) -> None:
    client, services, clock = env
    add_user(services, "active@example.org", MEMBER_PASSWORD)
    add_user(services, "off@example.org", MEMBER_PASSWORD, active=False)
    invited = client.post(
        "/api/admin/users", json={"email": "new@example.org", "role": "admin"}
    ).json()
    sign_in(web_client(services), "active@example.org", MEMBER_PASSWORD)

    users = {u["email"]: u for u in client.get("/api/admin/users").json()}
    assert set(users) == {ADMIN_EMAIL, "active@example.org", "off@example.org", "new@example.org"}
    assert users[ADMIN_EMAIL]["role"] == "admin" and users[ADMIN_EMAIL]["status"] == "active"
    assert users["active@example.org"]["status"] == "active"
    assert users["active@example.org"]["last_sign_in_at"] is not None
    assert users["off@example.org"]["status"] == "inactive"
    assert users["off@example.org"]["last_sign_in_at"] is None
    assert users["new@example.org"] == {
        **users["new@example.org"],
        "role": "admin",
        "status": "invited",
        "last_sign_in_at": None,
        "invite_expires_at": invited["expires_at"],
    }
    assert users[ADMIN_EMAIL]["invite_expires_at"] is None  # only pending users have one
    assert parse(users[ADMIN_EMAIL]["created_at"]) <= utc(clock.now)


def test_the_list_never_exposes_password_or_token_hashes(env: Env) -> None:
    client, _, _ = env
    invited = client.post(
        "/api/admin/users", json={"email": "new@example.org", "role": "member"}
    ).json()
    text = client.get("/api/admin/users").text
    assert "argon2" not in text and "hash" not in text and invited["token"] not in text


# ---- inviting -------------------------------------------------------------------------------
def test_inviting_creates_a_pending_user_and_a_single_use_link(env: Env) -> None:
    client, services, clock = env
    res = client.post("/api/admin/users", json={"email": "new@example.org", "role": "member"})
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["email"] == "new@example.org" and body["user"]["role"] == "member"
    assert body["user"]["status"] == "invited"
    assert len(body["token"]) >= 43
    assert (
        body["invite_path"] == f"/accept-invite#token={body['token']}"
    )  # fragment: not sent to servers
    assert parse(body["expires_at"]) == utc(clock.now) + timedelta(hours=168)  # 7 days
    assert usable(services, clock, body["token"])
    # the invited person cannot sign in until they accept
    res = web_client(services).post(
        "/api/auth/login", json={"email": "new@example.org", "password": "anything long enough"}
    )
    assert res.status_code == 401


def test_the_invite_lifetime_is_configurable(tmp_path: Path) -> None:
    clock = FakeClock()
    with running(tmp_path, clock, auth_invite_ttl_hours=2) as (client, _):
        sign_in(client)
        body = client.post(
            "/api/admin/users", json={"email": "n@example.org", "role": "member"}
        ).json()
    assert parse(body["expires_at"]) == utc(clock.now) + timedelta(hours=2)


def test_the_email_is_normalised_and_duplicates_are_refused(env: Env) -> None:
    client, services, _ = env
    assert (
        client.post(
            "/api/admin/users", json={"email": "  New@Example.ORG ", "role": "member"}
        ).status_code
        == 201
    )
    assert "new@example.org" in user_emails(services)
    for email in ("new@example.org", "NEW@example.org", ADMIN_EMAIL):
        res = client.post("/api/admin/users", json={"email": email, "role": "member"})
        assert res.status_code == 409
        assert res.json() == {
            "code": "user_exists",
            "message": "A user with this email address already exists.",
        }
    assert user_emails(services).count("new@example.org") == 1


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"email": "not-an-email", "role": "member"}, "email"),
        ({"email": "a@b.org", "role": "superuser"}, "role"),
        ({"email": "", "role": ""}, "email"),
    ],
)
def test_invalid_input_is_a_field_error_and_creates_nothing(
    env: Env, payload: dict[str, str], field: str
) -> None:
    client, services, _ = env
    res = client.post("/api/admin/users", json=payload)
    assert res.status_code == 422 and res.json()["code"] == "validation_error"
    assert field in res.json()["errors"]
    assert user_emails(services) == [ADMIN_EMAIL]


def test_the_role_defaults_to_member(env: Env) -> None:
    client, _, _ = env
    assert (
        client.post("/api/admin/users", json={"email": "n@example.org"}).json()["user"]["role"]
        == "member"
    )


# ---- re-issuing -----------------------------------------------------------------------------
def test_a_new_link_replaces_the_old_one(env: Env) -> None:
    client, services, clock = env
    first = client.post(
        "/api/admin/users", json={"email": "n@example.org", "role": "member"}
    ).json()
    clock.advance(hours=1)
    second = client.post(f"/api/admin/users/{first['user']['id']}/invite")
    assert second.status_code == 200
    body = second.json()
    assert body["token"] != first["token"]
    assert not usable(services, clock, first["token"])  # the old link is dead
    assert usable(services, clock, body["token"])
    assert parse(body["expires_at"]) == utc(clock.now) + timedelta(hours=168)
    listed = next(u for u in client.get("/api/admin/users").json() if u["email"] == "n@example.org")
    assert listed["invite_expires_at"] == body["expires_at"]


def test_an_expired_invite_can_be_replaced(env: Env) -> None:
    client, services, clock = env
    first = client.post(
        "/api/admin/users", json={"email": "n@example.org", "role": "member"}
    ).json()
    clock.advance(days=8)  # the invite expires, and so does the admin's own idle session
    assert not usable(services, clock, first["token"])
    sign_in(client)
    fresh = client.post(f"/api/admin/users/{first['user']['id']}/invite").json()
    assert usable(services, clock, fresh["token"])


def test_only_pending_users_can_be_reinvited_or_revoked(env: Env) -> None:
    client, services, _ = env
    member_id = add_user(services, "member@example.org", MEMBER_PASSWORD)
    for response in (
        client.post(f"/api/admin/users/{member_id}/invite"),
        client.delete(f"/api/admin/users/{member_id}/invite"),
    ):
        assert response.status_code == 409 and response.json()["code"] == "user_not_pending"
    assert "member@example.org" in user_emails(services)  # still there


def test_unknown_users_are_a_404(env: Env) -> None:
    client, _, _ = env
    assert client.post("/api/admin/users/999/invite").json()["code"] == "user_not_found"
    assert client.delete("/api/admin/users/999/invite").status_code == 404


# ---- revoking -------------------------------------------------------------------------------
def test_revoking_withdraws_the_invite_and_frees_the_address(env: Env) -> None:
    client, services, clock = env
    invited = client.post(
        "/api/admin/users", json={"email": "n@example.org", "role": "member"}
    ).json()
    res = client.delete(f"/api/admin/users/{invited['user']['id']}/invite")
    assert res.status_code == 200
    assert "n@example.org" not in user_emails(services)
    assert not usable(services, clock, invited["token"])
    assert (
        client.post(
            "/api/admin/users", json={"email": "n@example.org", "role": "member"}
        ).status_code
        == 201
    )


# ---- storage --------------------------------------------------------------------------------
def test_the_raw_token_is_never_stored(env: Env) -> None:
    client, services, _ = env
    token = client.post(
        "/api/admin/users", json={"email": "n@example.org", "role": "member"}
    ).json()["token"]
    services.db.engine.dispose()
    assert token.encode() not in services.db.path.read_bytes()
    with services.db.session() as db:
        from app.models import Invite

        row = db.scalars(select(Invite)).one()
        assert row.kind == TOKEN_INVITE and row.token_hash != token and row.used_at is None
