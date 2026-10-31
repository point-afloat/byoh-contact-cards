import base64
import json
import logging

import httpx
import pytest
import respx

from app.config import load_settings
from app.contact import CONTACT_FIELDS
from app.extraction import (
    INCOMPLETE_NOTICE,
    MAX_TOKENS,
    ExtractionClient,
    ExtractionError,
    parse_contact,
)
from app.images import PreparedImage

BASE = "https://llm.example/v1"
URL = BASE + "/chat/completions"
IMAGE = PreparedImage(data=b"\xff\xd8fake-jpeg-bytes", media_type="image/jpeg", width=10, height=10)


def make_client(**overrides: object) -> ExtractionClient:
    settings = load_settings(
        _env_file=None,
        llm_base_url=BASE,
        llm_model="tiny-vision",
        llm_api_key="secret-llm-key",
        **overrides,
    )
    return ExtractionClient(settings)


def chat(content: object) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


GOOD = json.dumps(
    {"first_name": "Anna", "last_name": "Meier", "company": "Acme", "email": "a@acme.org"}
)


@respx.mock
def test_success_returns_contact_with_values_in_matching_fields() -> None:
    respx.post(URL).mock(return_value=chat(GOOD))
    result = make_client().extract(IMAGE)
    assert result.contact.first_name == "Anna"
    assert result.contact.email == "a@acme.org"
    assert result.contact.phone == ""
    assert result.incomplete is False and result.notice is None


@respx.mock
def test_request_carries_model_cap_temperature_image_and_key() -> None:
    route = respx.post(URL).mock(return_value=chat(GOOD))
    make_client().extract(IMAGE)
    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["model"] == "tiny-vision"
    assert body["temperature"] == 0
    assert body["max_tokens"] == MAX_TOKENS
    fmt = body["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["name"] == "contact" and fmt["json_schema"]["strict"] is True
    image_part = body["messages"][1]["content"][1]
    expected = "data:image/jpeg;base64," + base64.b64encode(IMAGE.data).decode()
    assert image_part["image_url"]["url"] == expected
    assert request.headers["authorization"] == "Bearer secret-llm-key"


@respx.mock
def test_markdown_fenced_and_chatty_output_is_tolerated() -> None:
    route = respx.post(URL).mock(return_value=chat("Sure!\n```json\n" + GOOD + "\n```"))
    result = make_client().extract(IMAGE)
    assert result.contact.last_name == "Meier"
    assert route.call_count == 1


@respx.mock
def test_chunked_content_is_supported() -> None:
    respx.post(URL).mock(return_value=chat([{"type": "text", "text": GOOD}]))
    assert make_client().extract(IMAGE).contact.company == "Acme"


@respx.mock
def test_invalid_field_values_are_dropped_and_flagged_incomplete() -> None:
    bad = json.dumps({"first_name": "Anna", "company": {"nested": 1}, "phone": 12345})
    respx.post(URL).mock(return_value=chat(bad))
    result = make_client().extract(IMAGE)
    assert result.contact.first_name == "Anna"
    assert result.contact.company == ""
    assert result.contact.phone == "12345"
    assert result.incomplete is True
    assert result.notice == INCOMPLETE_NOTICE


@respx.mock
def test_malformed_response_is_retried_once_then_succeeds() -> None:
    route = respx.post(URL).mock(side_effect=[chat("not json at all"), chat(GOOD)])
    result = make_client().extract(IMAGE)
    assert route.call_count == 2
    assert result.contact.first_name == "Anna"


@respx.mock
def test_malformed_twice_gives_empty_incomplete_result_after_one_retry() -> None:
    route = respx.post(URL).mock(return_value=chat("still not json"))
    result = make_client().extract(IMAGE)
    assert route.call_count == 2
    assert result.contact.first_name == ""
    assert result.incomplete is True


@respx.mock
def test_json_without_any_known_keys_counts_as_malformed() -> None:
    route = respx.post(URL).mock(return_value=chat('{"unrelated": "x"}'))
    result = make_client().extract(IMAGE)
    assert route.call_count == 2
    assert result.incomplete is True


@respx.mock
def test_unreachable_raises_extraction_error_without_retry() -> None:
    route = respx.post(URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(ExtractionError) as exc:
        make_client().extract(IMAGE)
    assert exc.value.code == "extraction_unreachable"
    assert route.call_count == 1


@respx.mock
def test_timeout_raises_extraction_error() -> None:
    respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ExtractionError) as exc:
        make_client().extract(IMAGE)
    assert exc.value.code == "extraction_timeout"


@respx.mock
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "extraction_unauthorized"),
        (429, "extraction_rate_limited"),
        (500, "extraction_failed"),
    ],
)
def test_error_statuses_map_to_codes_and_never_echo_the_body(status: int, code: str) -> None:
    respx.post(URL).mock(return_value=httpx.Response(status, text="secret-llm-key leaked?"))
    with pytest.raises(ExtractionError) as exc:
        make_client().extract(IMAGE)
    assert exc.value.code == code
    assert "secret-llm-key" not in str(exc.value)


@respx.mock
def test_card_content_and_key_are_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    respx.post(URL).mock(return_value=chat(GOOD))
    with caplog.at_level(logging.DEBUG):
        make_client().extract(IMAGE)
    assert "Anna" not in caplog.text
    assert "secret-llm-key" not in caplog.text


def test_parse_contact_returns_none_for_garbage() -> None:
    assert parse_contact("") is None
    assert parse_contact("[1, 2, 3]") is None


@respx.mock
def test_switching_base_url_model_and_key_needs_no_code_change() -> None:
    mistral = respx.post("https://api.mistral.ai/v1/chat/completions").mock(return_value=chat(GOOD))
    local = respx.post("http://localhost:1234/v1/chat/completions").mock(return_value=chat(GOOD))

    hosted = ExtractionClient(
        load_settings(_env_file=None, llm_model="small-hosted", llm_api_key="k")
    )
    hosted.extract(IMAGE)
    assert mistral.call_count == 1 and local.call_count == 0
    assert json.loads(mistral.calls.last.request.content)["model"] == "small-hosted"

    switched = ExtractionClient(
        load_settings(
            _env_file=None, llm_base_url="http://localhost:1234/v1", llm_model="local-model"
        )
    )
    switched.extract(IMAGE)
    assert local.call_count == 1 and mistral.call_count == 1
    request = local.calls.last.request
    assert json.loads(request.content)["model"] == "local-model"
    assert "authorization" not in request.headers  # no key configured for the local endpoint


def response_format_of(call: respx.models.Call) -> dict[str, object]:
    fmt: dict[str, object] = json.loads(call.request.content)["response_format"]
    return fmt


@respx.mock
def test_request_asks_for_a_strict_schema_with_all_contact_fields() -> None:
    route = respx.post(URL).mock(return_value=chat(GOOD))
    make_client().extract(IMAGE)
    schema = response_format_of(route.calls.last)["json_schema"]["schema"]  # type: ignore[index]
    assert list(schema["properties"]) == list(CONTACT_FIELDS)
    assert schema["required"] == list(CONTACT_FIELDS)
    assert schema["additionalProperties"] is False
    assert all(p["type"] == "string" for p in schema["properties"].values())
    assert "default" not in json.dumps(schema)


@respx.mock
def test_unsupported_schema_falls_back_once_to_json_object_and_remembers() -> None:
    rejected = httpx.Response(400, json={"message": "response_format json_schema is not supported"})
    route = respx.post(URL).mock(side_effect=[rejected, chat(GOOD), chat(GOOD)])
    client = make_client()

    result = client.extract(IMAGE)
    assert result.contact.first_name == "Anna" and route.call_count == 2
    assert response_format_of(route.calls[0])["type"] == "json_schema"
    assert response_format_of(route.calls[1]) == {"type": "json_object"}

    client.extract(IMAGE)  # the downgrade sticks: no new json_schema attempt
    assert route.call_count == 3
    assert response_format_of(route.calls[2]) == {"type": "json_object"}


@respx.mock
def test_other_400_errors_do_not_trigger_the_fallback() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(400, json={"message": "image too big"})
    )
    with pytest.raises(ExtractionError) as exc:
        make_client().extract(IMAGE)
    assert exc.value.code == "extraction_failed" and route.call_count == 1


@respx.mock
def test_json_object_can_be_forced_by_configuration() -> None:
    route = respx.post(URL).mock(return_value=chat(GOOD))
    client = make_client(llm_response_format="json_object")
    client.extract(IMAGE)
    assert response_format_of(route.calls.last) == {"type": "json_object"}


@respx.mock
def test_non_conforming_output_is_still_handled_with_structured_output() -> None:
    bad = json.dumps({"first_name": "Anna", "company": ["not", "a", "string"]})
    respx.post(URL).mock(return_value=chat(bad))
    result = make_client().extract(IMAGE)
    assert result.contact.first_name == "Anna" and result.contact.company == ""
    assert result.incomplete is True
