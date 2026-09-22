# src/ingestion/ingestion.py

import base64
import io
import json
import logging
import os
import time

import easyocr
import httpx
import numpy as np
import pytesseract
from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

load_dotenv()

LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:1234/v1/chat/completions")
LOCAL_LLM_MODEL_NAME = os.getenv("LOCAL_LLM_MODEL_NAME", "qwen3-vl-4b")

_easyocr_reader: easyocr.Reader | None = None


class ExtractedField(BaseModel):
    text: str
    confidence: float | None = None


def _get_easyocr_reader() -> easyocr.Reader:
    """Lazy-load EasyOCR reader (it's expensive to initialize)."""
    global _easyocr_reader
    if _easyocr_reader is None:
        logger.info("Loading EasyOCR model (first use, this may take a moment)...")
        _easyocr_reader = easyocr.Reader(["en"])
        logger.info("EasyOCR model loaded.")
    return _easyocr_reader


def extract_with_tesseract(image: Image.Image) -> list[ExtractedField]:
    """Extract text using Tesseract OCR. Fast, but weak on handwriting."""
    start = time.monotonic()
    text = pytesseract.image_to_string(image)
    elapsed = time.monotonic() - start
    lines = [line for line in text.splitlines() if line.strip()]
    logger.info("Tesseract extracted %d lines in %.2fs", len(lines), elapsed)
    return [ExtractedField(text=line, confidence=None) for line in lines]


def extract_with_easyocr(image: Image.Image) -> list[ExtractedField]:
    """Extract text using EasyOCR. Slower, but generally better on messy handwriting."""
    reader = _get_easyocr_reader()
    img_array = np.array(image)

    start = time.monotonic()
    results = reader.readtext(img_array)
    elapsed = time.monotonic() - start
    logger.info("EasyOCR extracted %d fields in %.2fs", len(results), elapsed)

    return [
        ExtractedField(text=str(text), confidence=float(confidence))
        for (_bbox, text, confidence) in results
    ]


def extract_with_local_vlm(image: Image.Image) -> list[ExtractedField]:
    """Extract fields using a local Qwen3-VL model via LM Studio's local server."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    payload = {
        "model": LOCAL_LLM_MODEL_NAME,
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

    logger.info(
        "Sending request to Qwen3-VL via LM Studio (%s)...", LOCAL_LLM_MODEL_NAME
    )
    start = time.monotonic()

    try:
        response = httpx.post(LOCAL_LLM_URL, json=payload, timeout=120)
        response.raise_for_status()
    except httpx.ConnectError as e:
        logger.error("Could not reach LM Studio at %s", LOCAL_LLM_URL)
        raise RuntimeError(
            "Could not reach LM Studio's local server. "
            "Make sure LM Studio is running with a Qwen3-VL model loaded "
            f"and serving at {LOCAL_LLM_URL}."
        ) from e

    elapsed = time.monotonic() - start
    logger.info("Qwen3-VL responded in %.2fs", elapsed)

    content = response.json()["choices"][0]["message"]["content"]

    try:
        raw = json.loads(content)
        return [ExtractedField(**item) for item in raw]
    except (json.JSONDecodeError, ValidationError):
        logger.warning(
            "Qwen3-VL did not return valid JSON; returning raw text instead."
        )
        return [ExtractedField(text=content, confidence=None)]


def extract_fields(image: Image.Image, engine: str = "easyocr") -> list[ExtractedField]:
    """Extract fields from a card image using the chosen OCR engine."""
    engines = {
        "tesseract": extract_with_tesseract,
        "easyocr": extract_with_easyocr,
        "local_vlm": extract_with_local_vlm,
    }
    if engine not in engines:
        logger.error("Unknown engine requested: %r", engine)
        raise ValueError(f"Unknown engine: {engine!r}. Choose from {list(engines)}.")

    logger.info("Starting extraction with engine=%s", engine)
    return engines[engine](image)
