# tests/test_ingestion.py

import pytest
from PIL import Image

from ingestion.ingestion import ExtractedField, extract_fields, extract_with_tesseract


def _dummy_image() -> Image.Image:
    return Image.new("RGB", (10, 10))


def test_extract_fields_unknown_engine_raises():
    with pytest.raises(ValueError):
        extract_fields(image=_dummy_image(), engine="not_a_real_engine")


def test_extract_fields_error_message_lists_valid_engines():
    with pytest.raises(ValueError) as exc_info:
        extract_fields(image=_dummy_image(), engine="bogus")

    message = str(exc_info.value)
    assert "tesseract" in message
    assert "easyocr" in message
    assert "local_vlm" in message


def test_extract_with_tesseract_returns_extracted_fields():
    result = extract_with_tesseract(_dummy_image())
    assert all(isinstance(f, ExtractedField) for f in result)
