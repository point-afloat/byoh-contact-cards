from collections.abc import Iterator

import pytest

from app.config import Settings, get_settings

# Every setting is an environment variable named after its field, so the list can never go stale.
_ENV_VARS = [name.upper() for name in Settings.model_fields]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make sure the developer's real environment never leaks into tests.

    That covers environment variables and the `.env` file, which the settings class reads
    by itself, so a developer's own `.env` cannot change what a test sees.
    """
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()  # settings are cached; never carry them from one test to the next
    yield
    get_settings.cache_clear()
