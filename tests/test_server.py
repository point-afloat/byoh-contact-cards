import pytest

from app.errors import ConfigError
from app.server import DEFAULT_PORT, port_from_env


def test_port_defaults_to_8080_when_not_set() -> None:
    assert DEFAULT_PORT == 8080
    assert port_from_env({}) == 8080
    assert port_from_env({"PORT": ""}) == 8080
    assert port_from_env({"PORT": "  "}) == 8080


def test_port_can_be_overridden() -> None:
    assert port_from_env({"PORT": "9000"}) == 9000
    assert port_from_env({"PORT": " 3000 "}) == 3000


def test_port_is_read_from_the_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "8123")
    assert port_from_env() == 8123


@pytest.mark.parametrize("bad", ["abc", "80.5", "0", "70000", "-1"])
def test_invalid_port_is_a_clear_error(bad: str) -> None:
    with pytest.raises(ConfigError) as exc:
        port_from_env({"PORT": bad})
    assert "PORT" in str(exc.value)
