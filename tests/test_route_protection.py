"""Every API route needs a signed-in user unless it is explicitly public; CSRF guard."""

import io
import re
from pathlib import Path

import httpx
import respx
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.fundraisingbox.client import PERSONS_URL
from app.main import create_app
from tests.auth_helpers import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    CSRF_HEADER,
    NO_FRONTEND_BUILD,
    make_services,
    running,
    sign_in,
    web_client,
)

# The ONLY routes that may be used without signing in. Adding to this list is a security decision.
PUBLIC_ROUTES = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/invite-info",  # a link is its own credential: a 256-bit single-use token
    "/api/auth/accept-invite",
}
LLM_URL = "https://llm.example/v1/chat/completions"


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def api_operations(app: FastAPI) -> list[tuple[str, str]]:
    """Every (METHOD, path) under /api, read from the app's public OpenAPI schema."""
    operations: list[tuple[str, str]] = []
    for path, item in app.openapi()["paths"].items():
        if path.startswith("/api"):
            operations += [(method.upper(), path) for method in item if method in HTTP_METHODS]
    return operations


def anonymous_status(client: TestClient, method: str, path: str) -> int:
    concrete = re.sub(r"\{[^}]+\}", "anything", path)  # fill in path parameters
    return int(client.request(method, concrete, json={}).status_code)


def open_to_anonymous(client: TestClient, app: FastAPI) -> set[str]:
    """Paths that answer an anonymous caller with anything other than 401."""
    return {
        path
        for method, path in api_operations(app)
        if anonymous_status(client, method, path) != 401
    }


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), (1, 2, 3)).save(buf, format="JPEG")
    return buf.getvalue()


# ---- every route is protected unless explicitly public ---------------------------------------
def test_only_the_explicit_public_routes_answer_an_anonymous_caller(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    app = create_app(services, static_dir=NO_FRONTEND_BUILD)
    with TestClient(app, base_url="https://testserver", headers=CSRF_HEADER) as client:
        assert len(api_operations(app)) >= 10, "too few operations found: the enumeration is broken"
        assert open_to_anonymous(client, app) == PUBLIC_ROUTES


def test_the_check_would_catch_a_route_that_forgot_protection(tmp_path: Path) -> None:
    app = create_app(make_services(tmp_path), static_dir=NO_FRONTEND_BUILD)
    rogue = APIRouter()

    @rogue.get("/api/secret-by-mistake")
    def secret() -> dict[str, str]:
        return {"oops": "open"}

    app.include_router(rogue)  # added before the schema is first built
    with TestClient(app, base_url="https://testserver", headers=CSRF_HEADER) as client:
        assert open_to_anonymous(client, app) - PUBLIC_ROUTES == {"/api/secret-by-mistake"}


def test_the_enumeration_covers_the_routes_that_must_be_protected(tmp_path: Path) -> None:
    app = create_app(make_services(tmp_path), static_dir=NO_FRONTEND_BUILD)
    found = set(api_operations(app))
    assert {
        ("POST", "/api/sessions"),
        ("GET", "/api/sessions/{session_id}"),
        ("PUT", "/api/sessions/{session_id}"),
        ("POST", "/api/sessions/{session_id}/send"),
        ("GET", "/api/sessions/{session_id}/image"),
        ("GET", "/api/companies"),
        ("GET", "/api/app-info"),
        ("GET", "/api/auth/me"),
        ("POST", "/api/auth/logout"),
        ("POST", "/api/auth/change-password"),
    } <= found


# ---- anonymous callers get a 401 and nothing happens -----------------------------------------
@respx.mock
def test_anonymous_calls_get_401_and_cause_no_side_effects(tmp_path: Path) -> None:
    llm = respx.post(LLM_URL).mock(return_value=httpx.Response(200, json={}))
    fundraisingbox = respx.route(url__startswith=PERSONS_URL.rsplit("/", 1)[0]).mock(
        return_value=httpx.Response(200, json={})
    )
    with running(tmp_path) as (client, services):  # never signed in
        calls = [
            client.post("/api/sessions", files={"file": ("c.jpg", jpeg(), "image/jpeg")}),
            client.get("/api/sessions/abc"),
            client.get("/api/sessions/abc/image"),
            client.put("/api/sessions/abc", json={"last_name": "X"}),
            client.post(
                "/api/sessions/abc/send", json={"contact": {}, "company": {"mode": "none"}}
            ),
            client.get("/api/companies", params={"q": "Acme"}),
            client.get("/api/auth/me"),
            client.post("/api/auth/logout"),
            client.post(
                "/api/auth/change-password",
                json={
                    "current_password": ADMIN_PASSWORD,
                    "new_password": "another long passphrase",
                },
            ),
        ]
        assert len(services.store) == 0  # no review session was created
    for response in calls:
        assert response.status_code == 401, response.request.url
        assert response.json() == {"code": "not_authenticated", "message": "Please sign in."}
    assert llm.call_count == 0 and fundraisingbox.call_count == 0  # nothing reached the outside


def test_anonymous_calls_never_leak_data_in_the_401_body(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        text = client.get("/api/sessions/anything").text
    assert set(__import__("json").loads(text)) == {"code", "message"}


def test_the_health_check_works_without_signing_in(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        res = client.get("/api/health")
    assert res.status_code == 200 and res.json() == {"status": "ok"}


def test_a_signed_in_user_gets_through_the_same_routes(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        sign_in(client)
        assert (
            client.get("/api/sessions/abc").status_code == 404
        )  # reached the route: no such session
        assert client.get("/api/auth/me").status_code == 200


# ---- CSRF guard -------------------------------------------------------------------------------
def signed_in_without_csrf_header(tmp_path: Path) -> tuple[TestClient, TestClient]:
    """A signed-in browser session, replayed by a client that sends no custom header."""
    services = make_services(tmp_path)
    good = web_client(services)
    good.__enter__()  # runs startup (migration + first admin)
    sign_in(good)
    plain = TestClient(
        create_app(services, static_dir=NO_FRONTEND_BUILD), base_url="https://testserver"
    )
    plain.cookies.update(good.cookies)
    return good, plain


@respx.mock
def test_a_cross_site_style_upload_is_blocked_even_with_a_valid_session(tmp_path: Path) -> None:
    llm = respx.post(LLM_URL).mock(return_value=httpx.Response(200, json={}))
    good, plain = signed_in_without_csrf_header(tmp_path)
    try:
        res = plain.post("/api/sessions", files={"file": ("c.jpg", jpeg(), "image/jpeg")})
    finally:
        good.__exit__(None, None, None)
    assert res.status_code == 403 and res.json()["code"] == "csrf_blocked"
    assert llm.call_count == 0


def test_a_form_post_without_the_header_cannot_change_the_password(tmp_path: Path) -> None:
    good, plain = signed_in_without_csrf_header(tmp_path)
    try:
        res = plain.post(
            "/api/auth/change-password",
            data={"current_password": ADMIN_PASSWORD, "new_password": "another long passphrase"},
        )
        still_works = web_client(good.app.state.services)  # type: ignore[attr-defined]
        login = still_works.post(
            "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
    finally:
        good.__exit__(None, None, None)
    assert res.status_code == 403 and res.json()["code"] == "csrf_blocked"
    assert login.status_code == 200  # the original password is unchanged


def test_put_patch_and_delete_without_the_header_are_blocked_too(tmp_path: Path) -> None:
    good, plain = signed_in_without_csrf_header(tmp_path)
    try:
        responses = [
            plain.put("/api/sessions/abc", content=b"x=1", headers={"content-type": "text/plain"}),
            plain.patch(
                "/api/sessions/abc", content=b"x=1", headers={"content-type": "text/plain"}
            ),
            plain.delete("/api/sessions/abc", headers={"content-type": "text/plain"}),
        ]
    finally:
        good.__exit__(None, None, None)
    assert [r.status_code for r in responses] == [403, 403, 403]


def test_json_bodies_and_the_custom_header_both_pass_the_guard(tmp_path: Path) -> None:
    good, plain = signed_in_without_csrf_header(tmp_path)
    try:
        by_json = plain.post(
            "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        by_header = plain.post("/api/auth/logout", headers={"X-Requested-With": "fetch"})
    finally:
        good.__exit__(None, None, None)
    assert by_json.status_code == 200 and by_header.status_code == 200


def test_reading_needs_no_csrf_header(tmp_path: Path) -> None:
    good, plain = signed_in_without_csrf_header(tmp_path)
    try:
        assert plain.get("/api/auth/me").status_code == 200
        assert plain.get("/api/health").status_code == 200
    finally:
        good.__exit__(None, None, None)
