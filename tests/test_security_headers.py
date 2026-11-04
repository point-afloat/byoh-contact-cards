"""Security headers (request-hardening: "Security response headers" and "Transport security
and caching headers")."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.security_headers import CONTENT_SECURITY_POLICY
from tests.auth_helpers import CSRF_HEADER, make_services, running

ALWAYS = {
    "content-security-policy": CONTENT_SECURITY_POLICY,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
}


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text("<!doctype html><title>x</title><div id=root></div>")
    (site / "assets" / "app-abc123.js").write_text("console.log('app')")
    return site


def app_client(tmp_path: Path, dist: Path, **settings: object) -> TestClient:
    services = make_services(tmp_path, **settings)
    return TestClient(
        create_app(services, static_dir=dist), base_url="https://testserver", headers=CSRF_HEADER
    )


def check_always(headers: object) -> None:
    for name, value in ALWAYS.items():
        assert headers.get(name) == value, name  # type: ignore[attr-defined]


def test_the_start_page_and_an_api_response_carry_the_headers(tmp_path: Path, dist: Path) -> None:
    with app_client(tmp_path, dist) as client:
        check_always(client.get("/").headers)
        check_always(client.get("/api/health").headers)
        check_always(client.get("/assets/app-abc123.js").headers)


def test_the_policy_allows_only_the_apps_own_sources_and_forbids_framing() -> None:
    directives = dict(part.split(" ", 1) for part in CONTENT_SECURITY_POLICY.split("; "))
    assert directives["default-src"] == "'self'"
    assert directives["script-src"] == "'self'"  # no inline scripts, no eval, no other host
    assert directives["style-src"] == "'self'"  # no <style> blocks
    assert directives["connect-src"] == "'self'"
    assert "blob:" in directives["img-src"].split()  # the card preview
    assert directives["frame-ancestors"] == "'none'"
    assert directives["base-uri"] == "'none'"
    assert directives["object-src"] == "'none'"
    assert "*" not in CONTENT_SECURITY_POLICY and "unsafe-eval" not in CONTENT_SECURITY_POLICY


def test_errors_sent_before_the_router_carry_the_headers_too(tmp_path: Path, dist: Path) -> None:
    with app_client(tmp_path, dist) as client:
        too_large = client.post(
            "/api/sessions",
            content=b"x",
            headers={
                "content-length": "999999999",
                "content-type": "multipart/form-data; boundary=x",
            },
        )
        assert too_large.status_code == 413
        check_always(too_large.headers)
        anonymous = client.post("/api/sessions", files={"file": ("c.jpg", b"x", "image/jpeg")})
        assert anonymous.status_code == 401
        check_always(anonymous.headers)
        check_always(client.get("/api/nothing-here").headers)  # a 404


def test_the_headers_are_sent_even_when_the_app_is_not_configured() -> None:
    with TestClient(create_app()) as bare:  # no environment: settings cannot be built
        check_always(bare.get("/api/health").headers)


def test_api_responses_are_never_cached(tmp_path: Path, dist: Path) -> None:
    with app_client(tmp_path, dist) as client:
        assert client.get("/api/health").headers["cache-control"] == "no-store"
        assert client.get("/api/auth/me").headers["cache-control"] == "no-store"  # a 401
        assert client.get("/api/nothing-here").headers["cache-control"] == "no-store"
        assert client.get("/assets/app-abc123.js").headers.get("cache-control") != "no-store"
        assert client.get("/").headers["cache-control"] == "no-cache"  # the page keeps its rule


def test_strict_transport_security_follows_the_cookie_setting(tmp_path: Path, dist: Path) -> None:
    with app_client(tmp_path / "secure", dist) as secure:
        hsts = secure.get("/api/health").headers["strict-transport-security"]
        assert hsts == "max-age=15552000"
        assert "includesubdomains" not in hsts.lower() and "preload" not in hsts.lower()
        assert "strict-transport-security" in secure.get("/").headers
    with app_client(tmp_path / "plain", dist, auth_cookie_secure=False) as plain:
        assert "strict-transport-security" not in plain.get("/api/health").headers
        assert "strict-transport-security" not in plain.get("/").headers
        check_always(plain.get("/api/health").headers)  # the other headers do not depend on it


def test_the_running_helper_app_has_them_as_well(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        check_always(client.get("/api/health").headers)
