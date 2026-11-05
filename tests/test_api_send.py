import io
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from PIL import Image

from app.fundraisingbox.client import EMAILS_URL, PERSONS_URL, PHONES_URL
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


def mock_details() -> tuple[respx.Route, respx.Route]:
    """Routes for the email and phone records a CARD send creates after the person."""
    email = respx.post(EMAILS_URL).mock(return_value=httpx.Response(201, json={"id": 501}))
    phone = respx.post(PHONES_URL).mock(return_value=httpx.Response(201, json={"id": 502}))
    return email, phone


def fb_bodies(route: respx.Route) -> list[dict[str, object]]:
    return [json.loads(call.request.content) for call in route.calls]


@respx.mock
def test_success_creates_the_person_and_discards_card_data(client: TestClient) -> None:
    email_route, phone_route = mock_details()
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 733}))
    session_id = open_session(client)
    res = send(client, session_id, CARD)
    assert res.status_code == 200
    body = res.json()
    assert body["sent"] is True and body["person_id"] == "733" and body["record_type"] == "person"
    assert body["contact"] is None

    (sent,) = fb_bodies(route)
    assert sent["last_name"] == "Meier" and sent["first_name"] == "Anna"
    assert sent["fb_custom_fields"] == [{"id": 16786, "value": "Sync"}]
    info = str(sent.get("info", ""))
    assert "Email" not in info and "Phone" not in info  # they are records of their own
    assert "Company: Acme GmbH" in info  # not linked: kept as a note
    assert "company_name" not in sent and "company_id" not in sent
    assert fb_bodies(email_route) == [
        {"fb_person_id": 733, "email": "anna@acme.org", "type": "work", "is_main": True}
    ]
    assert fb_bodies(phone_route) == [
        {"fb_person_id": 733, "phone": "+49 30 1234", "type": "work", "is_main": True}
    ]

    assert client.get(f"/api/sessions/{session_id}/image").status_code == 410


@respx.mock
def test_nothing_is_sent_until_confirmed(client: TestClient) -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 1}))
    session_id = open_session(client)
    client.put(f"/api/sessions/{session_id}", json=CARD)
    assert route.call_count == 0


@respx.mock
def test_linking_an_existing_company_sends_company_id(client: TestClient) -> None:
    mock_details()
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 5}))
    session_id = open_session(client)
    res = send(client, session_id, CARD, {"mode": "link", "id": 77})
    assert res.status_code == 200
    (sent,) = fb_bodies(route)
    assert sent["company_id"] == 77 and "Company:" not in str(sent.get("info", ""))


@respx.mock
def test_creating_a_company_creates_it_first_then_links_the_person(client: TestClient) -> None:
    mock_details()
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
    mock_details()
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
    mock_details()
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
    mock_details()
    respx.post(PERSONS_URL).mock(
        side_effect=[httpx.ConnectError("down"), httpx.Response(201, json={"id": 2})]
    )
    session_id = open_session(client)
    failed = send(client, session_id, CARD)
    assert failed.status_code == 502 and failed.json()["code"] == "fundraisingbox_unreachable"
    assert send(client, session_id, CARD).status_code == 200


@respx.mock
def test_retry_after_person_failure_does_not_create_the_company_twice(client: TestClient) -> None:
    mock_details()
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
    assert res.status_code == 422 and res.json()["code"] == "validation_error"
    assert "notes" in res.json()["errors"]
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
    mock_details()
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
    mock_details()
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


# ---- mock mode: the payload preview ------------------------------------------------------------
@pytest.fixture
def mock_setup(tmp_path: Path) -> Iterator[tuple[TestClient, Services]]:
    services = make_services(
        tmp_path, llm_base_url="https://llm.example/v1", fundraisingbox_mode="mock"
    )
    with web_client(services) as test_client:
        sign_in(test_client)
        yield test_client, services


def test_a_mock_send_returns_what_would_have_been_sent_and_calls_nobody(
    mock_setup: tuple[TestClient, Services],
) -> None:
    client, _ = mock_setup
    session_id = open_session(client)
    with respx.mock(assert_all_called=False) as router:  # no routes: a request would fail
        res = send(client, session_id, CARD)
        assert router.calls.call_count == 0
    assert res.status_code == 200
    body = res.json()
    assert body["sent"] is True and body["person_id"].startswith("9") and body["contact"] is None
    preview = body["demo_payload"]
    payload = preview["person"]
    assert payload["last_name"] == "Meier" and payload["first_name"] == "Anna"
    assert "Email" not in payload.get("info", "")
    assert payload["fb_custom_fields"] == [{"id": 16786, "value": "Sync"}]
    (email,) = preview["emails"]
    assert email["email"] == "anna@acme.org" and email["fb_person_id"] == int(body["person_id"])
    (phone,) = preview["phones"]
    assert phone["phone"] == "+49 30 1234"
    payload = preview
    # the preview stays available while the session lives
    assert client.get(f"/api/sessions/{session_id}").json()["demo_payload"] == payload


def test_a_mock_company_only_send_returns_the_company_payload(
    mock_setup: tuple[TestClient, Services],
) -> None:
    client, _ = mock_setup
    session_id = open_session(client, {"company": "Neu & Gut e.V."})
    res = send(client, session_id, {"company": "Neu & Gut e.V."}, {"mode": "create"})
    assert res.status_code == 200 and res.json()["record_type"] == "company"
    assert res.json()["demo_payload"] == {
        "company": {
            "is_company": True,
            "company_name": "Neu & Gut e.V.",
        }
    }


def test_a_mock_person_with_a_new_company_shows_the_linked_company_id(
    mock_setup: tuple[TestClient, Services],
) -> None:
    client, _ = mock_setup
    session_id = open_session(client)
    res = send(client, session_id, CARD, {"mode": "create"})
    payload = res.json()["demo_payload"]["person"]
    assert isinstance(payload["company_id"], int) and payload["company_id"] >= 900001
    assert "Company:" not in payload.get("info", "")


@respx.mock
def test_a_live_send_returns_no_payload(client: TestClient) -> None:
    mock_details()
    respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 733}))
    session_id = open_session(client)
    res = send(client, session_id, CARD)
    assert res.status_code == 200 and res.json()["demo_payload"] is None
    assert client.get(f"/api/sessions/{session_id}").json()["demo_payload"] is None


def test_the_preview_is_gone_with_the_session(mock_setup: tuple[TestClient, Services]) -> None:
    client, services = mock_setup
    session_id = open_session(client)
    send(client, session_id, CARD)
    services.store.discard(session_id)
    gone = client.get(f"/api/sessions/{session_id}")
    assert gone.status_code == 404 and "demo_payload" not in gone.text


def test_a_refused_mock_send_shows_nothing_and_stays_open(
    mock_setup: tuple[TestClient, Services],
) -> None:
    client, _ = mock_setup
    session_id = open_session(client)
    res = send(client, session_id, {**CARD, "notes": "x" * 2000})
    assert res.status_code == 422 and "notes" in res.json()["errors"]
    assert client.get(f"/api/sessions/{session_id}").json()["sent"] is False


# ---- person first, then one request per detail ---------------------------------------------------
FULL_CARD = {
    **CARD,
    "mobile": "+49 170 1",
    "street": "Hauptstr. 1",
    "postal_code": "10115",
    "city": "Berlin",
    "country": "Deutschland",
    "website": "https://acme.org",
}


def all_routes() -> dict[str, respx.Route]:
    from app.fundraisingbox.client import ADDRESSES_URL, WEBSITES_URL

    ids = {"person": 700, "email": 701, "phone": 702, "address": 703, "website": 704}
    urls = {
        "person": PERSONS_URL,
        "email": EMAILS_URL,
        "phone": PHONES_URL,
        "address": ADDRESSES_URL,
        "website": WEBSITES_URL,
    }
    return {
        k: respx.post(urls[k]).mock(return_value=httpx.Response(201, json={"id": ids[k]}))
        for k in urls
    }


@respx.mock
def test_a_full_card_sends_the_person_then_each_detail_with_the_new_id(
    client: TestClient,
) -> None:
    routes = all_routes()
    session_id = open_session(client, FULL_CARD)
    res = send(client, session_id, FULL_CARD)
    assert res.status_code == 200 and res.json()["person_id"] == "700"
    assert [call.request.url.path for r in routes.values() for call in r.calls] == [
        "/v1/persons.json",
        "/v1/personEmailAddresses.json",
        "/v1/personPhones.json",
        "/v1/personPhones.json",
        "/v1/personAddresses.json",
        "/v1/personWebsites.json",
    ]
    phones = fb_bodies(routes["phone"])
    assert [p["type"] for p in phones] == ["work", "other"]
    assert [p["is_main"] for p in phones] == [True, False]
    assert fb_bodies(routes["address"])[0]["country"] == "DE"
    for name in ("email", "phone", "address", "website"):
        assert all(b["fb_person_id"] == 700 for b in fb_bodies(routes[name]))


@respx.mock
def test_a_card_with_only_a_name_sends_only_the_person(client: TestClient) -> None:
    routes = all_routes()
    card = {"last_name": "Meier"}
    session_id = open_session(client, card)
    assert send(client, session_id, card).status_code == 200
    assert routes["person"].call_count == 1
    assert sum(r.call_count for k, r in routes.items() if k != "person") == 0


@respx.mock
def test_a_company_only_card_attaches_its_details_to_the_company(client: TestClient) -> None:
    routes = all_routes()
    card = {"company": "Acme GmbH", "email": "info@acme.org"}
    session_id = open_session(client, card)
    res = send(client, session_id, card, {"mode": "create"})
    assert res.status_code == 200 and res.json()["record_type"] == "company"
    assert fb_bodies(routes["email"])[0]["fb_person_id"] == 700


@respx.mock
def test_nothing_is_created_when_a_limit_is_exceeded(client: TestClient) -> None:
    routes = all_routes()
    card = {**CARD, "phone": "1" * 51, "city": "x" * 101}
    session_id = open_session(client, card)
    res = send(client, session_id, card, {"mode": "create"})
    assert res.status_code == 422 and set(res.json()["errors"]) == {"phone", "city"}
    assert sum(r.call_count for r in routes.values()) == 0


@respx.mock
def test_a_failure_part_way_keeps_the_person_and_a_retry_sends_only_what_is_missing(
    client: TestClient,
) -> None:
    routes = all_routes()
    routes["phone"].mock(side_effect=[httpx.Response(400), httpx.Response(201, json={"id": 800})])
    session_id = open_session(client)
    failed = send(client, session_id, CARD)
    assert failed.status_code == 502 and failed.json()["code"] == "partly_sent"
    assert "phone" in failed.json()["message"] and "email" not in failed.json()["message"]
    assert client.get(f"/api/sessions/{session_id}").json()["sent"] is False

    corrected = {**CARD, "phone": "+49 30 9999"}
    retry = send(client, session_id, corrected)
    assert retry.status_code == 200 and retry.json()["person_id"] == "700"
    assert routes["person"].call_count == 1  # never a second person
    assert routes["email"].call_count == 1  # finished steps are not repeated
    assert fb_bodies(routes["phone"])[1]["phone"] == "+49 30 9999"


@respx.mock
def test_a_second_failure_is_reported_again_and_the_session_stays_open(
    client: TestClient,
) -> None:
    routes = all_routes()
    routes["phone"].mock(return_value=httpx.Response(400))
    session_id = open_session(client)
    for _ in range(2):
        res = send(client, session_id, CARD)
        assert res.status_code == 502 and res.json()["code"] == "partly_sent"
    assert routes["person"].call_count == 1
    assert client.get(f"/api/sessions/{session_id}").json()["sent"] is False
