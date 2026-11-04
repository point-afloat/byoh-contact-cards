"""No password, token, session id or email address may ever reach the logs.

The test records every log message while the app is started and every auth flow is exercised,
then checks that none of the secrets used along the way appear in any of them. The invite and
reset flows are added to this test together with those endpoints.
"""

import logging
from pathlib import Path

import pytest

from tests.auth_helpers import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    SESSION_COOKIE,
    FakeClock,
    add_user,
    running,
    sign_in,
    web_client,
)

WRONG_1 = "wrong-guess-password-one"
WRONG_2 = "wrong-guess-password-two"
NEW_PASSWORD = "brand new secret passphrase"
MEMBER_EMAIL = "member@example.org"
MEMBER_PASSWORD = "member's own long password"
BOGUS_COOKIE = "bogus-cookie-value-xyz-123"
GHOST_EMAIL = "ghost@example.org"
INVITED_EMAIL = "invited@example.org"
JOINER_EMAIL = "joiner@example.org"
JOINER_PASSWORD = "the joiner chose this passphrase"
RESET_PASSWORD = "the joiner reset to this passphrase"


def test_no_secret_reaches_the_logs_in_any_auth_flow(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)  # everything, from every library
    clock = FakeClock()
    secrets: set[str] = {
        ADMIN_PASSWORD, WRONG_1, WRONG_2, NEW_PASSWORD, MEMBER_PASSWORD, BOGUS_COOKIE,
        ADMIN_EMAIL, MEMBER_EMAIL, GHOST_EMAIL, INVITED_EMAIL, JOINER_EMAIL,
        JOINER_PASSWORD, RESET_PASSWORD,
    }  # fmt: skip

    with running(tmp_path, clock) as (client, services):  # startup: migration + first admin
        add_user(services, MEMBER_EMAIL, MEMBER_PASSWORD)

        # sign in, use the session, sign out
        sign_in(client)
        secrets.add(str(client.cookies.get(SESSION_COOKIE)))
        client.get("/api/auth/me")
        client.post("/api/auth/logout")

        # failures: wrong password, unknown email, then throttling until blocked
        for _ in range(3):
            client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": WRONG_1})
        client.post("/api/auth/login", json={"email": GHOST_EMAIL, "password": WRONG_2})
        for _ in range(4):
            client.post("/api/auth/login", json={"email": MEMBER_EMAIL, "password": WRONG_2})
        client.post(
            "/api/auth/login", json={"email": MEMBER_EMAIL, "password": MEMBER_PASSWORD}
        )  # 429
        clock.advance(minutes=11)

        # a made-up session cookie
        client.cookies.clear()
        client.cookies.set(SESSION_COOKIE, BOGUS_COOKIE)
        client.get("/api/auth/me")
        client.cookies.clear()

        # a real session: expires, then signs in again and changes the password
        sign_in(client)
        secrets.add(str(client.cookies.get(SESSION_COOKIE)))
        clock.advance(hours=13)  # idle expiry
        client.get("/api/auth/me")
        sign_in(client)
        secrets.add(str(client.cookies.get(SESSION_COOKIE)))
        client.post(
            "/api/auth/change-password",
            json={"current_password": WRONG_1, "new_password": NEW_PASSWORD},  # wrong current
        )
        client.post(
            "/api/auth/change-password",
            json={"current_password": ADMIN_PASSWORD, "new_password": NEW_PASSWORD},
        )

        # invitations: create, re-issue, revoke (the raw tokens are the secrets here)
        invited = client.post(
            "/api/admin/users", json={"email": INVITED_EMAIL, "role": "member"}
        ).json()
        user_id = invited["user"]["id"]
        again = client.post(f"/api/admin/users/{user_id}/invite").json()
        client.delete(f"/api/admin/users/{user_id}/invite")
        secrets.update({invited["token"], again["token"]})

        # accepting an invitation: the link and the chosen password are both secrets
        joiner = client.post(
            "/api/admin/users", json={"email": JOINER_EMAIL, "role": "member"}
        ).json()
        secrets.add(joiner["token"])
        visitor = web_client(services)
        visitor.post("/api/auth/invite-info", json={"token": joiner["token"]})
        visitor.post(
            "/api/auth/accept-invite", json={"token": joiner["token"], "password": "short"}
        )
        visitor.post(
            "/api/auth/accept-invite", json={"token": joiner["token"], "password": JOINER_PASSWORD}
        )
        secrets.add(str(visitor.cookies.get(SESSION_COOKIE)))
        visitor.post(
            "/api/auth/accept-invite", json={"token": joiner["token"], "password": JOINER_PASSWORD}
        )

        # admin actions and a password reset: the reset link and the new password are secrets
        joiner_id = joiner["user"]["id"]
        client.patch(f"/api/admin/users/{joiner_id}", json={"is_active": False})
        client.patch(f"/api/admin/users/{joiner_id}", json={"is_active": True})
        client.patch(f"/api/admin/users/{joiner_id}", json={"role": "admin"})
        reset = client.post(f"/api/admin/users/{joiner_id}/reset-link").json()
        secrets.add(reset["token"])
        resetter = web_client(services)
        resetter.post(
            "/api/auth/accept-invite", json={"token": reset["token"], "password": RESET_PASSWORD}
        )
        secrets.add(str(resetter.cookies.get(SESSION_COOKIE)))

    text = caplog.text
    assert "Created the first administrator account" in text  # the capture really worked
    assert len(caplog.records) > 3
    leaked = sorted(secret for secret in secrets if secret and secret in text)
    assert leaked == [], f"secrets found in the logs: {leaked}"


def test_failed_sign_ins_leave_no_log_record_naming_the_user(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with running(tmp_path) as (client, _):
        caplog.clear()
        caplog.set_level(logging.DEBUG)
        client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": WRONG_1})
    assert ADMIN_EMAIL not in caplog.text and WRONG_1 not in caplog.text
