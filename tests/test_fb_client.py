import json
import logging

import httpx
import pytest
import respx

from app.config import load_settings
from app.contact import Contact
from app.errors import ConfigError
from app.fundraisingbox.client import (
    PERSONS_URL,
    CompanyMatch,
    FundraisingBoxApiError,
    FundraisingBoxClient,
    FundraisingBoxNetworkError,
)

TOKEN = "fb-secret-token"
CONTACT = Contact(first_name="Anna", last_name="Meier", email="anna@private.example")


def make_client(token: str | None = TOKEN) -> FundraisingBoxClient:
    settings = load_settings(
        _env_file=None,
        llm_model="m",
        llm_api_key="k",
        fundraisingbox_apitoken=token,
    )
    return FundraisingBoxClient(settings)


@respx.mock
def test_create_person_success_returns_id_and_uses_basic_auth() -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 733}))
    created = make_client().create_person(CONTACT, company_id=5)
    assert created.id == 733
    request = route.calls.last.request
    assert request.headers["authorization"].startswith("Basic ")
    body = json.loads(request.content)
    assert body["last_name"] == "Meier" and body["company_id"] == 5
    assert body["fb_custom_fields"][0]["value"] == "Sync"


@respx.mock
def test_create_company_returns_id_and_sends_company_payload() -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 90}))
    assert make_client().create_company("Acme GmbH").id == 90
    body = json.loads(route.calls.last.request.content)
    assert body["is_company"] is True and body["company_name"] == "Acme GmbH"


@respx.mock
def test_search_companies_parses_matches() -> None:
    route = respx.get(PERSONS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": 7,
                        "company_name": "Acme GmbH",
                        "fb_person_addresses": [{"city": "Berlin"}],
                    },
                    {"id": 8, "company_name": "Acme AG"},
                    {"id": 9},  # no company name: ignored
                ]
            },
        )
    )
    matches = make_client().search_companies("Acme")
    assert matches == [CompanyMatch(7, "Acme GmbH", "Berlin"), CompanyMatch(8, "Acme AG", None)]
    assert route.calls.last.request.url.params["company"] == "Acme"


@respx.mock
def test_blank_search_makes_no_request() -> None:
    route = respx.get(PERSONS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
    assert make_client().search_companies("   ") == []
    assert route.call_count == 0


@respx.mock
@pytest.mark.parametrize("status", [400, 422, 500])
def test_error_statuses_raise_api_error_with_status_and_message(status: int) -> None:
    respx.post(PERSONS_URL).mock(
        return_value=httpx.Response(status, json={"first_name": ["not_editable"]})
    )
    with pytest.raises(FundraisingBoxApiError) as exc:
        make_client().create_person(CONTACT)
    assert exc.value.status == status
    assert str(status) in str(exc.value) and "not_editable" in str(exc.value)


@respx.mock
def test_empty_error_body_gives_status_only_message() -> None:
    respx.post(PERSONS_URL).mock(return_value=httpx.Response(400, json={}))
    with pytest.raises(FundraisingBoxApiError) as exc:
        make_client().create_person(CONTACT)
    assert str(exc.value) == "FundraisingBox returned an error (400)."


@respx.mock
def test_network_failure_raises_network_error() -> None:
    respx.post(PERSONS_URL).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(FundraisingBoxNetworkError):
        make_client().create_person(CONTACT)


@respx.mock
def test_timeout_raises_network_error() -> None:
    respx.post(PERSONS_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(FundraisingBoxNetworkError):
        make_client().create_person(CONTACT)


@respx.mock
def test_missing_token_makes_no_request() -> None:
    route = respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"id": 1}))
    with pytest.raises(ConfigError) as exc:
        make_client(token=None).create_person(CONTACT)
    assert "FUNDRAISINGBOX_APITOKEN" in str(exc.value)
    assert route.call_count == 0


@respx.mock
def test_response_without_id_is_reported() -> None:
    respx.post(PERSONS_URL).mock(return_value=httpx.Response(201, json={"ok": True}))
    with pytest.raises(FundraisingBoxApiError):
        make_client().create_person(CONTACT)


@respx.mock
def test_token_and_contact_data_never_reach_logs_or_messages(
    caplog: pytest.LogCaptureFixture,
) -> None:
    respx.post(PERSONS_URL).mock(return_value=httpx.Response(500, text="boom"))
    with caplog.at_level(logging.DEBUG), pytest.raises(FundraisingBoxApiError) as exc:
        make_client().create_person(CONTACT)
    assert TOKEN not in caplog.text and TOKEN not in str(exc.value)
    assert "private.example" not in caplog.text
