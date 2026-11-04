import io
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from tests.auth_helpers import CSRF_HEADER, SESSION_COOKIE, running, sign_in

LLM_URL = "https://llm.example/v1/chat/completions"
GOOD = {"first_name": "Anna", "last_name": "Meier", "company": "Acme", "email": "a@acme.org"}


def jpeg(size: tuple[int, int] = (200, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 120, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def chat(content: dict[str, str] | str) -> httpx.Response:
    text = content if isinstance(content, str) else json.dumps(content)
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with running(tmp_path, upload_max_bytes=100_000, session_ttl_seconds=60) as (test_client, _):
        sign_in(test_client)
        yield test_client


def upload(
    client: TestClient, data: bytes, name: str = "card.jpg", mime: str = "image/jpeg"
) -> httpx.Response:
    response: httpx.Response = client.post("/api/sessions", files={"file": (name, data, mime)})
    return response


@respx.mock
def test_upload_extracts_and_opens_a_session(client: TestClient) -> None:
    respx.post(LLM_URL).mock(return_value=chat(GOOD))
    res = upload(client, jpeg())
    assert res.status_code == 201
    body = res.json()
    assert body["contact"]["first_name"] == "Anna" and body["contact"]["phone"] == ""
    assert body["warnings"] == [] and body["sent"] is False and len(body["id"]) > 30

    fetched = client.get(f"/api/sessions/{body['id']}")
    assert fetched.status_code == 200 and fetched.json() == body


@respx.mock
def test_card_image_is_served_back(client: TestClient) -> None:
    respx.post(LLM_URL).mock(return_value=chat(GOOD))
    session_id = upload(client, jpeg()).json()["id"]
    res = client.get(f"/api/sessions/{session_id}/image")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert res.headers["cache-control"] == "no-store"
    assert Image.open(io.BytesIO(res.content)).size == (200, 100)


@respx.mock
def test_unsupported_upload_is_rejected_without_calling_the_model(client: TestClient) -> None:
    route = respx.post(LLM_URL).mock(return_value=chat(GOOD))
    res = upload(client, b"%PDF-1.7 fake", "card.pdf", "application/pdf")
    assert res.status_code == 415
    assert res.json()["code"] == "unsupported_file_type"
    assert "JPEG" in res.json()["message"]
    assert route.call_count == 0


@respx.mock
def test_oversized_upload_is_rejected_with_the_limit(client: TestClient) -> None:
    route = respx.post(LLM_URL).mock(return_value=chat(GOOD))
    res = upload(client, jpeg() + b"0" * 200_000)
    assert res.status_code == 413
    assert res.json()["code"] == "file_too_large"
    assert route.call_count == 0


def test_missing_file_field_is_a_validation_error(client: TestClient) -> None:
    res = client.post("/api/sessions")
    assert res.status_code == 422 and res.json()["code"] == "validation_error"


@respx.mock
def test_extraction_failure_leaves_an_empty_editable_contact(client: TestClient) -> None:
    respx.post(LLM_URL).mock(side_effect=httpx.ConnectError("down"))
    res = upload(client, jpeg())
    assert res.status_code == 201
    body = res.json()
    assert body["contact"]["first_name"] == "" and body["contact"]["last_name"] == ""
    assert len(body["warnings"]) == 1 and "could not be reached" in body["warnings"][0]

    saved = client.put(f"/api/sessions/{body['id']}", json={"last_name": "Typed by hand"})
    assert saved.status_code == 200 and saved.json()["contact"]["last_name"] == "Typed by hand"


@respx.mock
def test_malformed_model_output_gives_an_incomplete_notice(client: TestClient) -> None:
    respx.post(LLM_URL).mock(return_value=chat("not json"))
    body = upload(client, jpeg()).json()
    assert body["contact"]["last_name"] == "" and "incomplete" in body["warnings"][0]


@respx.mock
def test_put_replaces_the_contact(client: TestClient) -> None:
    respx.post(LLM_URL).mock(return_value=chat(GOOD))
    session_id = upload(client, jpeg()).json()["id"]
    res = client.put(f"/api/sessions/{session_id}", json={**GOOD, "first_name": "Berta"})
    assert res.status_code == 200 and res.json()["contact"]["first_name"] == "Berta"
    assert client.get(f"/api/sessions/{session_id}").json()["contact"]["first_name"] == "Berta"


def test_unknown_session_reports_expired(client: TestClient) -> None:
    responses = [
        client.get("/api/sessions/nope"),
        client.get("/api/sessions/nope/image"),
        client.put("/api/sessions/nope", json={}),
    ]
    for res in responses:
        assert res.status_code == 404 and res.json()["code"] == "session_expired"
        assert "scan the card again" in res.json()["message"]


def test_missing_llm_configuration_is_a_clear_503_not_a_crash() -> None:
    # A cookie is sent so the request gets past the early refusal of cookie-less uploads and
    # reaches the configuration check, which is what this test is about.
    headers = {**CSRF_HEADER, "cookie": f"{SESSION_COOKIE}=made-up"}
    with TestClient(create_app(), headers=headers) as bare:  # no env: settings cannot be built
        res = bare.post("/api/sessions", files={"file": ("c.jpg", jpeg(), "image/jpeg")})
    assert res.status_code == 503
    assert res.json()["code"] == "config_error" and "LLM_MODEL" in res.json()["message"]


@respx.mock
def test_saving_a_draft_reports_problems_without_blocking(client: TestClient) -> None:
    respx.post(LLM_URL).mock(return_value=chat(GOOD))
    session_id = upload(client, jpeg()).json()["id"]
    res = client.put(f"/api/sessions/{session_id}", json={"first_name": "Anna", "email": "bad"})
    assert res.status_code == 200
    errors = res.json()["errors"]
    assert {"last_name", "company", "email"} <= set(errors)
    assert client.get(f"/api/sessions/{session_id}").json()["errors"] == errors


@respx.mock
def test_valid_session_has_no_errors(client: TestClient) -> None:
    respx.post(LLM_URL).mock(return_value=chat(GOOD))
    assert upload(client, jpeg()).json()["errors"] == {}
