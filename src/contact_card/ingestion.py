# src/contact_card/ingestion.py

import base64
import io
import json

import easyocr
import httpx
import numpy as np
import pytesseract
from PIL import Image

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
LM_STUDIO_MODEL_NAME = "qwen3-vl-4b"

_easyocr_reader = None


def _get_easyocr_reader():
    """Lazy-load EasyOCR reader."""
    global _easyocr_reader
    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(["en"])
    return _easyocr_reader


def extract_with_tesseract(image: Image.Image) -> list[dict]:
    """Extract text using Tesseract OCR."""
    text = pytesseract.image_to_string(image)
    lines = [line for line in text.splitlines() if line.strip()]
    return [{"text": line, "confidence": None} for line in lines]


def extract_with_easyocr(image: Image.Image) -> list[dict]:
    """Extract text using EasyOCR."""
    reader = _get_easyocr_reader()
    img_array = np.array(image)
    results = reader.readtext(img_array)
    return [
        {"text": text, "confidence": confidence}
        for (_bbox, text, confidence) in results
    ]


def extract_with_qwen_vl(image: Image.Image) -> list[dict]:
    """Extract fields using a local Qwen3-VL model via LM Studio's local server.
    Requires LM Studio running locally (http://localhost:1234) with a Qwen3-VL model loaded.
    """
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    payload = {
        "model": LM_STUDIO_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract the contact fields from this handwritten card. "
                            "Return ONLY a JSON list of objects like "
                            '{"text": "...", "confidence": null} for each field you find. '
                            "No explanation, just the JSON."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "temperature": 0,
    }

    try:
        response = httpx.post(LM_STUDIO_URL, json=payload, timeout=120)
        response.raise_for_status()
    except httpx.ConnectError as e:
        raise RuntimeError(
            "Could not reach LM Studio's local server. "
            "Make sure LM Studio is running with a Qwen3-VL model loaded "
            f"and serving at {LM_STUDIO_URL}."
        ) from e

    content = response.json()["choices"][0]["message"]["content"]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Model didn't return clean JSON — surface the raw output instead of failing silently
        return [{"text": content, "confidence": None}]


def extract_fields(image: Image.Image, engine: str = "easyocr") -> list[dict]:
    """Extract fields from a card image using the chosen OCR engine.

    Args:
        image: the card image (already converted from PDF if needed).
        engine: one of "tesseract", "easyocr", "qwen_vl".

    Returns:
        A list of {"text": str, "confidence": float | None} dicts.
    """
    engines = {
        "tesseract": extract_with_tesseract,
        "easyocr": extract_with_easyocr,
        "qwen_vl": extract_with_qwen_vl,
    }
    if engine not in engines:
        raise ValueError(f"Unknown engine: {engine!r}. Choose from {list(engines)}.")
    return engines[engine](image)
