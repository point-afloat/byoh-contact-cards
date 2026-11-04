"""The size-limit middleware: first on its own through the ASGI interface, then in the real app."""

import asyncio
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from starlette import formparsers

from app.body_limit import ENVELOPE_ALLOWANCE_BYTES, JSON_LIMIT_BYTES, BodyLimit
from app.main import create_app, upload_limit_for
from app.models import LoginAttempt
from tests.auth_helpers import NO_FRONTEND_BUILD, make_services, running

UPLOAD_MAX = 1000
UPLOAD_LIMIT = UPLOAD_MAX + ENVELOPE_ALLOWANCE_BYTES


class Inner:
    """A stand-in app that reads the whole body like a framework would, then answers 200."""

    def __init__(self) -> None:
        self.called = False
        self.bytes_seen = 0
        self.saw_disconnect = False

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.called = True
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                self.saw_disconnect = True
                break
            self.bytes_seen += len(message.get("body", b""))
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


@dataclass
class Outcome:
    sent: list[dict[str, Any]] = field(default_factory=list)
    receive_calls: int = 0

    @property
    def starts(self) -> list[dict[str, Any]]:
        return [m for m in self.sent if m["type"] == "http.response.start"]

    @property
    def status(self) -> int:
        return int(self.starts[0]["status"])

    @property
    def body(self) -> dict[str, str]:
        raw = b"".join(m.get("body", b"") for m in self.sent if m["type"] == "http.response.body")
        parsed: dict[str, str] = json.loads(raw)
        return parsed


def call(
    app: Any,
    *,
    method: str = "POST",
    path: str = "/api/auth/login",
    headers: dict[str, str] | None = None,
    chunks: tuple[bytes, ...] = (b"",),
) -> Outcome:
    outcome = Outcome()
    queue = list(chunks)

    async def receive() -> dict[str, Any]:
        outcome.receive_calls += 1
        if queue:
            body = queue.pop(0)
            return {"type": "http.request", "body": body, "more_body": bool(queue)}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        outcome.sent.append(message)

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    asyncio.run(app(scope, receive, send))
    return outcome


@pytest.fixture
def inner() -> Inner:
    return Inner()


@pytest.fixture
def app(inner: Inner) -> BodyLimit:
    return BodyLimit(inner, upload_max_bytes=UPLOAD_MAX)


# ---- declared size ------------------------------------------------------------------------------
def test_declared_size_over_the_limit_is_refused_without_reading(app: BodyLimit, inner: Inner):
    result = call(app, headers={"content-length": str(JSON_LIMIT_BYTES + 1)})
    assert result.status == 413
    assert result.body == {"code": "request_too_large", "message": "The request is too large."}
    assert not inner.called
    assert result.receive_calls == 0  # not a single byte of the body was read


def test_the_refusal_asks_the_client_to_close_the_connection(app: BodyLimit):
    result = call(app, headers={"content-length": str(JSON_LIMIT_BYTES + 1)})
    headers = dict(result.starts[0]["headers"])
    assert headers[b"connection"] == b"close"
    assert headers[b"content-type"].startswith(b"application/json")


def test_json_at_exactly_the_limit_is_accepted(app: BodyLimit, inner: Inner):
    body = b"x" * JSON_LIMIT_BYTES
    result = call(app, headers={"content-length": str(len(body))}, chunks=(body,))
    assert result.status == 200
    assert inner.bytes_seen == JSON_LIMIT_BYTES


def test_a_bodyless_request_is_accepted(app: BodyLimit, inner: Inner):
    assert call(app, method="GET", path="/api/auth/me").status == 200
    assert inner.called


# ---- streamed size ------------------------------------------------------------------------------
def test_streamed_body_over_the_limit_is_cut_off_with_a_single_413(app: BodyLimit, inner: Inner):
    chunk = b"x" * 10_000
    chunks = tuple(chunk for _ in range(7))  # 70,000 bytes, no content-length header
    result = call(app, chunks=chunks)
    assert result.status == 413
    assert len(result.starts) == 1  # whatever the app tries to send afterwards is dropped
    assert inner.saw_disconnect
    assert inner.bytes_seen < 70_000  # the rest of the body was never handed to the app


def test_streamed_json_at_exactly_the_limit_is_accepted(app: BodyLimit, inner: Inner):
    half = JSON_LIMIT_BYTES // 2
    result = call(app, chunks=(b"x" * half, b"x" * half))
    assert result.status == 200
    assert inner.bytes_seen == JSON_LIMIT_BYTES


def test_one_byte_over_in_a_stream_is_refused(app: BodyLimit):
    half = JSON_LIMIT_BYTES // 2
    assert call(app, chunks=(b"x" * half, b"x" * (half + 1))).status == 413


def test_an_understated_content_length_does_not_let_a_larger_body_through(
    app: BodyLimit, inner: Inner
):
    result = call(app, headers={"content-length": "10"}, chunks=(b"x" * (JSON_LIMIT_BYTES + 1),))
    assert result.status == 413
    assert len(result.starts) == 1


# ---- the card upload ----------------------------------------------------------------------------
def test_upload_may_be_larger_than_json_up_to_the_limit(app: BodyLimit, inner: Inner):
    body = b"x" * UPLOAD_LIMIT
    result = call(
        app, path="/api/sessions", headers={"content-length": str(len(body))}, chunks=(body,)
    )
    assert result.status == 200
    assert inner.bytes_seen == UPLOAD_LIMIT


def test_upload_over_the_limit_is_refused_by_its_declared_size(app: BodyLimit, inner: Inner):
    result = call(app, path="/api/sessions", headers={"content-length": str(UPLOAD_LIMIT + 1)})
    assert result.status == 413
    assert result.body == {"code": "file_too_large", "message": "The file is too large."}
    assert not inner.called
    assert result.receive_calls == 0


def test_upload_over_the_limit_is_cut_off_when_streamed(app: BodyLimit, inner: Inner):
    result = call(app, path="/api/sessions", chunks=(b"x" * UPLOAD_LIMIT, b"x"))
    assert result.status == 413
    assert result.body["code"] == "file_too_large"
    assert len(result.starts) == 1


def test_the_upload_allowance_applies_only_to_the_upload_route(app: BodyLimit, inner: Inner):
    result = call(app, path="/api/auth/login", headers={"content-length": str(UPLOAD_LIMIT)})
    assert result.status == 413 and not inner.called


def test_only_a_post_to_the_upload_route_gets_the_larger_limit(app: BodyLimit):
    result = call(
        app, method="PUT", path="/api/sessions", headers={"content-length": str(UPLOAD_LIMIT)}
    )
    assert result.status == 413


def test_the_upload_limit_is_looked_up_for_every_request(inner: Inner):
    current = {"max": 1000}
    app = BodyLimit(inner, upload_max_bytes=lambda: current["max"])
    size = 5000 + ENVELOPE_ALLOWANCE_BYTES
    refused = call(app, path="/api/sessions", headers={"content-length": str(size)})
    current["max"] = 5000
    accepted = call(
        app, path="/api/sessions", headers={"content-length": str(size)}, chunks=(b"x" * size,)
    )
    assert (refused.status, accepted.status) == (413, 200)


# ---- an invalid length --------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["abc", "-5", "1e3", "12 34", "", "0x10", "1.5"])
def test_a_content_length_that_is_not_a_whole_number_is_a_400(
    app: BodyLimit, inner: Inner, value: str
):
    result = call(app, headers={"content-length": value})
    assert result.status == 400
    assert result.body["code"] == "invalid_content_length"
    assert not inner.called
    assert result.receive_calls == 0


# ---- things that are not requests ---------------------------------------------------------------
def test_other_scope_types_pass_straight_through():
    seen: list[str] = []

    async def lifespan_app(scope: Any, receive: Any, send: Any) -> None:
        seen.append(scope["type"])

    wrapped: Any = BodyLimit(lifespan_app, upload_max_bytes=UPLOAD_MAX)
    asyncio.run(wrapped({"type": "lifespan"}, None, None))
    assert seen == ["lifespan"]


def test_an_app_failure_before_any_overflow_is_not_hidden():
    async def broken(scope: Any, receive: Any, send: Any) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        call(BodyLimit(broken, upload_max_bytes=UPLOAD_MAX))


def test_an_app_that_fails_after_the_body_was_cut_off_does_not_raise():
    async def reads_then_fails(scope: Any, receive: Any, send: Any) -> None:
        while (await receive())["type"] == "http.request":
            pass
        raise RuntimeError("client went away")

    result = call(
        BodyLimit(reads_then_fails, upload_max_bytes=UPLOAD_MAX),
        chunks=(b"x" * (JSON_LIMIT_BYTES + 1),),
    )
    assert result.status == 413


# ---- the real app -------------------------------------------------------------------------------
REAL_UPLOAD_MAX = 100_000
MULTIPART_HEAD = (
    b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.jpg"\r\n'
    b"Content-Type: image/jpeg\r\n\r\n"
)


@pytest.fixture
def multipart_parses(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Counts how often a multipart body is handed to the parser, to show it never was."""
    calls = {"n": 0}
    original = formparsers.MultiPartParser.parse

    async def spy(self: Any) -> Any:
        calls["n"] += 1
        return await original(self)

    monkeypatch.setattr(formparsers.MultiPartParser, "parse", spy)
    return calls


def test_the_size_limit_is_the_outermost_layer_of_the_app():
    app = create_app(static_dir=NO_FRONTEND_BUILD)
    assert app.user_middleware[0].cls is BodyLimit


def test_an_anonymous_oversized_upload_is_refused_and_never_parsed(
    tmp_path: Path, multipart_parses: dict[str, int]
):
    with running(tmp_path, upload_max_bytes=REAL_UPLOAD_MAX) as (client, services):
        big = b"0" * 5_000_000
        # The client is not signed in and sends the CSRF header, as an attacker's script would.
        response = client.post("/api/sessions", files={"file": ("a.jpg", big, "image/jpeg")})
        assert response.status_code == 413
        assert response.json() == {"code": "file_too_large", "message": "The file is too large."}
        assert multipart_parses["n"] == 0
        assert len(services.store) == 0


def streamed_upload() -> Iterator[bytes]:
    yield MULTIPART_HEAD
    for _ in range(60):
        yield b"0" * 100_000
    yield b"\r\n--x--\r\n"


STREAMED = {"content-type": "multipart/form-data; boundary=x"}  # sent in chunks, no length


def test_a_streamed_upload_over_the_limit_is_cut_off_with_413(tmp_path: Path):
    with running(tmp_path, upload_max_bytes=REAL_UPLOAD_MAX) as (client, services):
        response = client.post(
            "/api/sessions",
            content=streamed_upload(),
            headers={**STREAMED, "cookie": "session=made-up"},  # a cookie gets it past 401
        )
        assert response.status_code == 413
        assert response.json()["code"] == "file_too_large"
        assert len(services.store) == 0


def test_oversized_json_is_refused_before_the_login_route_runs(tmp_path: Path):
    with running(tmp_path) as (client, services):
        response = client.post(
            "/api/auth/login", json={"email": "a@example.org", "password": "x" * 70_000}
        )
        assert response.status_code == 413
        assert response.json()["code"] == "request_too_large"
        with services.db.session() as db:  # nothing was recorded about it
            assert db.scalar(select(func.count()).select_from(LoginAttempt)) == 0


def test_the_limit_comes_before_the_csrf_guard(tmp_path: Path):
    client = TestClient(create_app(make_services(tmp_path), static_dir=NO_FRONTEND_BUILD))
    plain = {"content-type": "text/plain"}  # no JSON body and no X-Requested-With header
    assert client.post("/api/auth/login", content=b"x", headers=plain).status_code == 403
    too_big = client.post("/api/auth/login", content=b"x" * 70_000, headers=plain)
    assert too_big.status_code == 413


def test_the_upload_limit_is_looked_up_from_the_settings_for_each_request(
    monkeypatch: pytest.MonkeyPatch,
):
    app = create_app(static_dir=NO_FRONTEND_BUILD)  # no services yet: settings load lazily
    assert upload_limit_for(app) == 10 * 1024 * 1024  # invalid configuration: the default

    monkeypatch.setenv("LLM_MODEL", "tiny")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "2000")
    assert upload_limit_for(app) == 2000


# ---- uploads without a session cookie ------------------------------------------------------------
@pytest.fixture
def gated(inner: Inner) -> BodyLimit:
    return BodyLimit(inner, upload_max_bytes=UPLOAD_MAX, session_cookie_name="session")


def test_an_upload_without_a_cookie_is_refused_unread(gated: BodyLimit, inner: Inner):
    result = call(
        gated, path="/api/sessions", headers={"content-length": "100"}, chunks=(b"x" * 100,)
    )
    assert result.status == 401
    assert result.body == {"code": "not_authenticated", "message": "Please sign in."}
    assert not inner.called
    assert result.receive_calls == 0


def test_a_streamed_upload_without_a_cookie_is_refused_unread(gated: BodyLimit, inner: Inner):
    result = call(gated, path="/api/sessions", chunks=(b"x" * 100,))
    assert result.status == 401
    assert not inner.called and result.receive_calls == 0


def test_the_declared_size_is_checked_before_the_cookie(gated: BodyLimit, inner: Inner):
    result = call(gated, path="/api/sessions", headers={"content-length": str(UPLOAD_LIMIT + 1)})
    assert result.status == 413 and not inner.called


@pytest.mark.parametrize("cookie", ["session=abc", "other=1; session=abc", "session=abc; other=1"])
def test_any_session_cookie_gets_the_upload_through(gated: BodyLimit, inner: Inner, cookie: str):
    result = call(gated, path="/api/sessions", headers={"cookie": cookie}, chunks=(b"x" * 10,))
    assert result.status == 200 and inner.called  # whether it is valid is the app's business


@pytest.mark.parametrize(
    "cookie", ["other=1", "session=", "sessionx=abc", "xsession=abc", "garbage"]
)
def test_a_missing_or_empty_session_cookie_does_not(gated: BodyLimit, inner: Inner, cookie: str):
    result = call(gated, path="/api/sessions", headers={"cookie": cookie}, chunks=(b"x" * 10,))
    assert result.status == 401 and not inner.called


def test_the_cookie_may_arrive_in_several_headers(gated: BodyLimit, inner: Inner):
    result = (
        Outcome()
    )  # HTTP/2 clients may split the cookie header; the harness takes one, so build by hand
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/sessions",
        "headers": [(b"cookie", b"other=1"), (b"cookie", b"session=abc")],
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"x", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        result.sent.append(message)

    asyncio.run(gated(scope, receive, send))  # type: ignore[arg-type]
    assert result.status == 200 and inner.called


def test_only_the_upload_route_needs_the_cookie(gated: BodyLimit, inner: Inner):
    assert call(gated, path="/api/auth/login", chunks=(b"{}",)).status == 200  # public route
    assert call(gated, method="GET", path="/api/sessions", chunks=(b"",)).status == 200
    assert call(gated, method="PUT", path="/api/sessions", chunks=(b"{}",)).status == 200
    assert call(gated, path="/api/sessions/abc/send", chunks=(b"{}",)).status == 200


def test_the_cookie_name_is_looked_up_for_every_request(inner: Inner):
    current = {"name": "session"}
    app = BodyLimit(inner, upload_max_bytes=UPLOAD_MAX, session_cookie_name=lambda: current["name"])
    headers = {"cookie": "__Host-session=abc"}
    before = call(app, path="/api/sessions", headers=headers, chunks=(b"x",))
    current["name"] = "__Host-session"
    after = call(app, path="/api/sessions", headers=headers, chunks=(b"x",))
    assert (before.status, after.status) == (401, 200)


def test_without_a_cookie_name_the_gate_is_off(app: BodyLimit, inner: Inner):
    assert call(app, path="/api/sessions", chunks=(b"x",)).status == 200


# ---- the real app, uploads without a session cookie ----------------------------------------------
def test_a_cookieless_upload_within_the_limit_is_refused_and_never_parsed(
    tmp_path: Path, multipart_parses: dict[str, int]
):
    with running(tmp_path, upload_max_bytes=REAL_UPLOAD_MAX) as (client, services):
        small = b"0" * 10_000  # within the limit, so only the cookie check can stop it
        response = client.post("/api/sessions", files={"file": ("a.jpg", small, "image/jpeg")})
        assert response.status_code == 401
        assert multipart_parses["n"] == 0
        assert len(services.store) == 0


def test_a_streamed_cookieless_upload_is_refused_and_never_parsed(
    tmp_path: Path, multipart_parses: dict[str, int]
):
    with running(tmp_path, upload_max_bytes=REAL_UPLOAD_MAX) as (client, _):
        response = client.post("/api/sessions", content=streamed_upload(), headers=STREAMED)
        assert response.status_code == 401
        assert multipart_parses["n"] == 0


def test_the_early_401_is_the_same_as_the_usual_one(tmp_path: Path):
    with running(tmp_path, upload_max_bytes=REAL_UPLOAD_MAX) as (client, _):
        early = client.post("/api/sessions", files={"file": ("a.jpg", b"0" * 10, "image/jpeg")})
        usual = client.get("/api/auth/me")
        assert early.status_code == usual.status_code == 401
        assert early.json() == usual.json()


def test_a_made_up_cookie_is_checked_in_the_usual_way(
    tmp_path: Path, multipart_parses: dict[str, int]
):
    with running(tmp_path, upload_max_bytes=REAL_UPLOAD_MAX) as (client, _):
        response = client.post(
            "/api/sessions",
            files={"file": ("a.jpg", b"0" * 10, "image/jpeg")},
            headers={"cookie": "session=made-up"},
        )
        assert response.status_code == 401  # refused by the sign-in check, after parsing
        assert multipart_parses["n"] == 1
