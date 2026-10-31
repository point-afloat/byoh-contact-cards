import logging

import pytest

from app.config import Settings, load_settings, require_fundraisingbox_token
from app.errors import ConfigError


def make(**kwargs: object) -> Settings:
    return load_settings(_env_file=None, **kwargs)


def test_missing_model_raises_clear_error() -> None:
    with pytest.raises(ConfigError) as exc:
        make(llm_api_key="k")
    assert "LLM_MODEL" in str(exc.value)


def test_missing_key_for_hosted_endpoint_raises_clear_error() -> None:
    with pytest.raises(ConfigError) as exc:
        make(llm_model="m")
    assert "LLM_API_KEY" in str(exc.value)


def test_local_endpoint_does_not_need_key() -> None:
    s = make(llm_model="m", llm_base_url="http://localhost:1234/v1")
    assert s.llm_api_key is None


def test_defaults_and_overrides() -> None:
    s = make(llm_model="m", llm_api_key="k")
    assert s.llm_base_url == "https://api.mistral.ai/v1"
    assert s.upload_max_bytes == 10 * 1024 * 1024
    s2 = make(llm_model="m", llm_api_key="k", llm_base_url="https://other/v1", llm_timeout=5)
    assert s2.llm_base_url == "https://other/v1"
    assert s2.llm_timeout == 5


def test_env_vars_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "from-env")
    monkeypatch.setenv("LLM_API_KEY", "key-from-env")
    assert make().llm_model == "from-env"


def test_secrets_not_in_repr_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    s = make(
        llm_model="m",
        llm_api_key="super-secret-llm",
        fundraisingbox_apitoken="super-secret-fb",
    )
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("t").info("settings=%s %r", s, s)
    assert "super-secret" not in repr(s)
    assert "super-secret" not in str(s)
    assert "super-secret" not in caplog.text


def test_missing_fundraisingbox_token_is_a_clear_config_error() -> None:
    s = make(llm_model="m", llm_api_key="k")
    with pytest.raises(ConfigError) as exc:
        require_fundraisingbox_token(s)
    assert "FUNDRAISINGBOX_APITOKEN" in str(exc.value)
    assert exc.value.code == "fundraisingbox_not_configured"


def test_fundraisingbox_token_returned_when_set() -> None:
    s = make(llm_model="m", llm_api_key="k", fundraisingbox_apitoken="tok")
    assert require_fundraisingbox_token(s) == "tok"


def test_response_format_defaults_to_json_schema_and_can_be_overridden() -> None:
    assert make(llm_model="m", llm_api_key="k").llm_response_format == "json_schema"
    assert (
        make(llm_model="m", llm_api_key="k", llm_response_format="json_object").llm_response_format
        == "json_object"
    )


def test_unknown_response_format_is_a_clear_error() -> None:
    with pytest.raises(ConfigError) as exc:
        make(llm_model="m", llm_api_key="k", llm_response_format="yaml")
    assert "LLM_RESPONSE_FORMAT" in str(exc.value)
