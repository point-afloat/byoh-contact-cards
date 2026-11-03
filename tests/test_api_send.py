import io
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from PIL import Image

from app.fundraisingbox.client import PERSONS_URL
from app.services import Services
from tests.auth_helpers import make_services, running, sign_in, web_client

LLM_URL = "https://llm.example/v1/chat/completions"
CARD = {
    "first_name": "Anna",
    "last_name": "Meier",
    "company": "Acme GmbH",
    "email": "anna@acme.org",
    "phone": "+49 30 1234",
}


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 60), (1, 2, 3)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def services(tmp_path: Path) -> Services:
    return make_services(tmp_path, llm_base_url="https://llm.example/v1")


@pytest.fixture
def client(services: Services) -> Iterator[TestClient]:
    with web_client(services) as test_client:
        sign_in(test_client)
        yield test_client


def open_session(client: TestClient, contact: dict[str, str] | None = None) -> str:
    content = json.dumps(contact if contact is not None else CARD)
    with respx.mock:
        respx.post(LLM_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
        )
        res = client.post("/api/sessions", files={"file": ("c.jpg", jpeg(), "image/jpeg")})
    assert res.status_code == 201
    session_id: str = res.json()["id"]
    return session_id


def send(
    client: TestClient,
    session_id: str,
    contact: dict[str, str],
    company: dict[str, object] | None = None,
) -> httpx.Response:
    body: dict[str, object] = {"contact": contact}
    if company is not None:
        body["company"] = company
    response: httpx.Response = client.post(f"/api/sessions/{session_id}/send", json=body)
    return response


def fb_bodies(route: respx.Route) -> list[dict[str, object]]:
    return [json.loads(call.request.content) for call in route.calls]


@respx.mock
def test_success_creates_the_person_and_discards_card_data(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 733}))
    session_id = open_session(client)
    res = send(client, session_id, CARD)
    assert res.status_code == 200
    body = res.json()
    assert body["sent"] is True and body["person_id"] == "733" and body["record_type"] == "person"
    assert body["contact"] is None

    (sent,) = fb_bodies(route)
    assert sent["last_name"] == "Meier" and sent["first_name"] == "Anna"
    assert sent["fb_custom_fields"] == [{"id": "16786", "name": "ContactPilot", "value": "Sync"}]
    info = str(sent["info"])
    assert "Email: anna@acme.org" in info and "Phone: +49 30 1234" in info
    assert "Company: Acme GmbH" in info  # not linked: kept as a note, like the prototype
    assert "company_name" not in sent and "company_id" not in sent

    assert client.get(f"/api/sessions/{session_id}/image").status_code == 410


@respx.mock
def test_nothing_is_sent_until_confirmed(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 1}))
    session_id = open_session(client)
    client.put(f"/api/sessions/{session_id}", json=CARD)
    assert route.call_count == 0


@respx.mock
def test_linking_an_existing_company_sends_company_id(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 5}))
    session_id = open_session(client)
    res = send(client, session_id, CARD, {"mode": "link", "id": 77})
    assert res.status_code == 200
    (sent,) = fb_bodies(route)
    assert sent["company_id"] == 77 and "Company:" not in str(sent["info"])


@respx.mock
def test_creating_a_company_creates_it_first_then_links_the_person(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(
        side_effect=[httpx.Response(201, json={"id": 90}), httpx.Response(201, json={"id": 91})]
    )
    session_id = open_session(client)
    res = send(client, session_id, CARD, {"mode": "create"})
    assert res.status_code == 200 and res.json()["person_id"] == "91"
    company, person = fb_bodies(route)
    assert company["is_company"] is True and company["company_name"] == "Acme GmbH"
    assert person["company_id"] == 90 and "is_company" not in person


@respx.mock
def test_company_only_card_creates_just_the_company(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 90}))
    card = {"company": "Acme GmbH"}
    session_id = open_session(client, card)
    res = send(client, session_id, card, {"mode": "create"})
    assert res.status_code == 200
    assert res.json()["record_type"] == "company" and res.json()["person_id"] == "90"
    (sent,) = fb_bodies(route)
    assert sent["is_company"] is True


@respx.mock
def test_company_only_card_without_creating_is_refused(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 1}))
    card = {"company": "Acme GmbH"}
    session_id = open_session(client, card)
    for choice in (None, {"mode": "link", "id": 3}):
        res = send(client, session_id, card, choice)
        assert res.status_code == 422 and res.json()["code"] == "nothing_to_create"
    assert route.call_count == 0


@respx.mock
def test_double_submit_creates_one_person(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 733}))
    session_id = open_session(client)
    assert send(client, session_id, CARD).status_code == 200
    again = send(client, session_id, CARD)
    assert again.status_code == 409 and again.json()["code"] == "already_sent"
    assert route.call_count == 1


@respx.mock
def test_concurrent_send_is_refused_while_one_is_in_flight(
    client: TestClient, services: Services
) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 1}))
    session_id = open_session(client)
    session = services.store.get(session_id)
    assert session.send_lock.acquire(blocking=False)  # simulate a send already running
    try:
        res = send(client, session_id, CARD)
    finally:
        session.send_lock.release()
    assert res.status_code == 409 and res.json()["code"] == "send_in_progress"
    assert route.call_count == 0


@respx.mock
def test_api_error_keeps_the_data_and_a_retry_succeeds(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(
        side_effect=[
            httpx.Response(400, json={"first_name": ["not_editable"]}),
            httpx.Response(201, json={"id": 8}),
        ]
    )
    session_id = open_session(client)
    failed = send(client, session_id, CARD)
    assert failed.status_code == 502 and "400" in failed.json()["message"]

    kept = client.get(f"/api/sessions/{session_id}").json()
    assert kept["sent"] is False and kept["contact"]["last_name"] == "Meier"
    assert client.get(f"/api/sessions/{session_id}/image").status_code == 200

    retry = send(client, session_id, CARD)
    assert retry.status_code == 200 and retry.json()["person_id"] == "8"
    assert route.call_count == 2


@respx.mock
def test_network_error_is_reported_and_retryable_without_reupload(client: TestClient) -> None:
    respx.post(PERSONS_URL).mock(
        side_effect=[httpx.ConnectError("down"), httpx.Response(201, json={"id": 2})]
    )
    session_id = open_session(client)
    failed = send(client, session_id, CARD)
    assert failed.status_code == 502 and failed.json()["code"] == "fundraisingbox_unreachable"
    assert send(client, session_id, CARD).status_code == 200


@respx.mock
def test_retry_after_person_failure_does_not_create_the_company_twice(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(
        side_effect=[
            httpx.Response(201, json={"id": 90}),  # company
            httpx.Response(500, text="boom"),  # person fails
            httpx.Response(201, json={"id": 91}),  # person on retry
        ]
    )
    session_id = open_session(client)
    assert send(client, session_id, CARD, {"mode": "create"}).status_code == 502
    assert send(client, session_id, CARD, {"mode": "create"}).status_code == 200
    bodies = fb_bodies(route)
    assert [b.get("is_company", False) for b in bodies] == [True, False, False]
    assert bodies[2]["company_id"] == 90


@respx.mock
def test_missing_token_makes_no_request(tmp_path: Path) -> None:
    bare = make_services(tmp_path, fundraisingbox_apitoken=None)
    with web_client(bare) as client:
        sign_in(client)
        route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 1}))
        session_id = open_session(client)
        res = send(client, session_id, CARD)
    assert res.status_code == 503 and res.json()["code"] == "fundraisingbox_not_configured"
    assert route.call_count == 0


@respx.mock
def test_invalid_contact_is_blocked_with_field_errors(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 1}))
    session_id = open_session(client)
    res = send(client, session_id, {"first_name": "Anna", "email": "bad"})
    assert res.status_code == 422 and res.json()["code"] == "validation_error"
    assert {"last_name", "company", "email"} <= set(res.json()["errors"])
    assert route.call_count == 0


@respx.mock
def test_over_long_info_blocks_before_anything_is_created(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 1}))
    session_id = open_session(client)
    res = send(client, session_id, {**CARD, "notes": "x" * 1200}, {"mode": "create"})
    assert res.status_code == 422 and res.json()["code"] == "info_too_long"
    assert route.call_count == 0  # not even the company was created


def test_link_choice_requires_an_id(client: TestClient) -> None:
    session_id = open_session(client)
    res = send(client, session_id, CARD, {"mode": "link"})
    assert res.status_code == 422 and res.json()["code"] == "validation_error"


def test_send_for_an_unknown_session_reports_expired(client: TestClient) -> None:
    res = send(client, "nope", CARD)
    assert res.status_code == 404 and res.json()["code"] == "session_expired"


@respx.mock
def test_sent_contact_is_not_editable_and_not_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 733}))
    with caplog.at_level("DEBUG"):
        session_id = open_session(client)
        send(client, session_id, CARD)
    assert "anna@acme.org" not in caplog.text
    assert "fb-secret-token-123" not in caplog.text
    edit = client.put(f"/api/sessions/{session_id}", json=CARD)
    assert edit.status_code == 409 and edit.json()["code"] == "already_sent"


@respx.mock
def test_processing_and_sending_a_card_writes_nothing_to_the_data_dir(tmp_path: Path) -> None:
    respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 1}))
    with running(tmp_path) as (client, _):
        sign_in(client)
        session_id = open_session(client)
        client.put(f"/api/sessions/{session_id}", json=CARD)
        assert send(client, session_id, CARD).status_code == 200
    # persistent storage is for accounts only: nothing but the account database, and no card
    # image or contact data inside it
    assert [p.name for p in tmp_path.iterdir()] == ["app.db"]
    assert b"anna@acme.org" not in (tmp_path / "app.db").read_bytes()
