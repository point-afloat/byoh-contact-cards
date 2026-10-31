from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import load_settings
from app.fundraisingbox.client import PERSONS_URL
from app.main import create_app
from app.services import build_services


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = load_settings(
        _env_file=None, llm_model="m", llm_api_key="k", fundraisingbox_apitoken="tok"
    )
    with TestClient(create_app(build_services(settings))) as test_client:
        yield test_client


@respx.mock
def test_match_returns_companies(client: TestClient) -> None:
    respx.get(PERSONS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": 7,
                        "company_name": "Acme GmbH",
                        "fb_person_addresses": [{"city": "Berlin"}],
                    }
                ]
            },
        )
    )
    res = client.get("/api/companies", params={"q": "Acme"})
    assert res.status_code == 200
    assert res.json() == [{"id": 7, "name": "Acme GmbH", "city": "Berlin"}]


@respx.mock
def test_no_match_returns_an_empty_list(client: TestClient) -> None:
    respx.get(PERSONS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
    res = client.get("/api/companies", params={"q": "Nobody"})
    assert res.status_code == 200 and res.json() == []


@respx.mock
def test_search_error_is_a_clear_502(client: TestClient) -> None:
    respx.get(PERSONS_URL).mock(return_value=httpx.Response(500, text="boom"))
    res = client.get("/api/companies", params={"q": "Acme"})
    assert res.status_code == 502
    assert res.json()["code"] == "fundraisingbox_rejected" and "500" in res.json()["message"]


@respx.mock
def test_unreachable_is_a_clear_502(client: TestClient) -> None:
    respx.get(PERSONS_URL).mock(side_effect=httpx.ConnectError("down"))
    res = client.get("/api/companies", params={"q": "Acme"})
    assert res.status_code == 502 and res.json()["code"] == "fundraisingbox_unreachable"


def test_blank_query_returns_empty_without_calling_fundraisingbox(client: TestClient) -> None:
    with respx.mock:
        route = respx.get(PERSONS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        assert client.get("/api/companies", params={"q": ""}).json() == []
        assert route.call_count == 0


def test_missing_token_is_a_503_config_error() -> None:
    settings = load_settings(_env_file=None, llm_model="m", llm_api_key="k")
    with TestClient(create_app(build_services(settings))) as bare:
        res = bare.get("/api/companies", params={"q": "Acme"})
    assert res.status_code == 503 and res.json()["code"] == "fundraisingbox_not_configured"
