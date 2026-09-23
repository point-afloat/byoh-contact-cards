# tests/test_ingestion.py

import httpx
import pytest
from PIL import Image

from ingestion.ingestion import (
    Contact,
    _extract_last_json_object,
    extract_fields,
    extract_with_local_vlm,
)


def _dummy_image() -> Image.Image:
    return Image.new("RGB", (10, 10))


class _FakeResponse:
    def __init__(self, message: dict) -> None:
        self._message = message

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"message": self._message}


def test_extract_fields_unknown_engine_raises():
    with pytest.raises(ValueError):
        extract_fields(image=_dummy_image(), engine="not_a_real_engine")


def test_extract_fields_error_message_lists_valid_engines():
    with pytest.raises(ValueError) as exc_info:
        extract_fields(image=_dummy_image(), engine="bogus")

    assert "local_vlm" in str(exc_info.value)


def test_extract_last_json_object_finds_last_balanced_object():
    text = 'draft: {"name": "old"} final answer: {"name": "Alice", "city": "NYC"}'
    assert _extract_last_json_object(text) == '{"name": "Alice", "city": "NYC"}'


def test_extract_last_json_object_returns_none_without_braces():
    assert _extract_last_json_object("no json here") is None


def test_extract_with_local_vlm_parses_content(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _FakeResponse({"role": "assistant", "content": '{"name": "Alice"}'}),
    )
    contact = extract_with_local_vlm(_dummy_image())
    assert contact == Contact(name="Alice")


def test_extract_with_local_vlm_falls_back_to_thinking_block(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _FakeResponse(
            {
                "role": "assistant",
                "content": "",
                "thinking": 'reasoning... {"name": "Bob"}',
            }
        ),
    )
    contact = extract_with_local_vlm(_dummy_image())
    assert contact == Contact(name="Bob")


def test_extract_with_local_vlm_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _FakeResponse({"role": "assistant", "content": "not json"}),
    )
    with pytest.raises(RuntimeError, match="did not return a valid Contact JSON"):
        extract_with_local_vlm(_dummy_image())


def test_extract_with_local_vlm_raises_runtime_error_on_connect_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "post", _raise)
    with pytest.raises(RuntimeError, match="Could not reach the local LLM server"):
        extract_with_local_vlm(_dummy_image())
