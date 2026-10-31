import pytest

_ENV_VARS = [
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_TIMEOUT",
    "LLM_RESPONSE_FORMAT",
    "FUNDRAISINGBOX_APITOKEN",
    "UPLOAD_MAX_BYTES",
    "SESSION_TTL_SECONDS",
    "SESSION_MAX_COUNT",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make sure the developer's real environment never leaks into tests."""
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
