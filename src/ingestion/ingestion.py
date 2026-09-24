# src/ingestion/ingestion.py

import base64
import io
import json
import logging
import os
import time

import httpx
from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

load_dotenv()

LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:1234").rstrip("/")
LOCAL_LLM_MODEL_NAME = os.getenv("LOCAL_LLM_MODEL_NAME", "qwen3-vl-4b")

LOCAL_LLM_TIMEOUT = 6000
# Safety net: cap generation length so a stuck/looping response fails fast
# instead of running for the full LOCAL_LLM_TIMEOUT.
LOCAL_LLM_NUM_PREDICT = 4096


def _extract_last_json_object(text: str) -> str | None:
    """Find the last top-level balanced {...} substring in text.

    Qwen3-VL forces its answer through a "thinking" block for image inputs
    (no known way to disable this for vision requests), so the JSON we want
    has to be pulled out of a field full of reasoning prose rather than read
    directly. The model's actual answer is consistently the last JSON object
    it writes, after any draft attempts earlier in its reasoning.
    """
    starts = [i for i, c in enumerate(text) if c == "{"]
    for start in reversed(starts):
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None


class Contact(BaseModel):
    """Structured contact fields extracted from a card.

    The Streamlit review page renders one input per field, driven off this
    model's field names — add/remove/rename a field here and the UI follows,
    no changes needed there.
    """

    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    job_title: str | None = None
    phone: str | None = None
    email: str | None = None
    street: str | None = None
    city: str | None = None


def extract_with_local_vlm(image: Image.Image) -> Contact:
    """Extract structured contact fields using a local vision LLM via Ollama.

    Uses Ollama's native /api/chat endpoint (rather than the OpenAI-compatible
    /v1/chat/completions one) so a reasoning-capable model can be configured
    with think=False if needed.
    """
    url = f"{LOCAL_LLM_BASE_URL}/api/chat"
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    payload = {
        "model": LOCAL_LLM_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Extract the contact's fields from this handwritten "
                    "or printed card and return them matching the given "
                    "schema. Leave a field null if it isn't present."
                ),
                "images": [image_b64],
            }
        ],
        "format": Contact.model_json_schema(),
        "think": False,
        "stream": False,
        "options": {
            # Fully greedy decoding (temperature=0) with no repeat penalty can
            # get stuck in a repetition loop inside an unconstrained JSON
            # string value and never reach the closing quote/brace before
            # hitting num_predict. A small temperature plus a repeat penalty
            # gives it enough randomness to break out of that.
            "temperature": 0.1,
            "repeat_penalty": 1.15,
            "num_predict": LOCAL_LLM_NUM_PREDICT,
        },
    }

    logger.info("Sending request to %s (model=%s)...", url, LOCAL_LLM_MODEL_NAME)
    start = time.monotonic()

    try:
        response = httpx.post(url, json=payload, timeout=LOCAL_LLM_TIMEOUT)
        response.raise_for_status()
    except httpx.ConnectError as e:
        logger.error("Could not reach the local LLM server at %s", url)
        raise RuntimeError(
            "Could not reach the local LLM server. Make sure it's running with "
            f"a vision model loaded and serving at {url}."
        ) from e
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"{url} returned {e.response.status_code}: {e.response.text}"
        ) from e

    elapsed = time.monotonic() - start
    logger.info("%s responded in %.2fs", LOCAL_LLM_MODEL_NAME, elapsed)

    message = response.json()["message"]
    content = message.get("content") or ""

    if not content.strip():
        logger.info("Empty content; falling back to parsing the thinking block.")
        content = _extract_last_json_object(message.get("thinking") or "") or ""

    try:
        return Contact.model_validate_json(content)
    except (json.JSONDecodeError, ValidationError) as e:
        raise RuntimeError(
            f"{LOCAL_LLM_MODEL_NAME} did not return a valid Contact JSON: {content!r}"
        ) from e


def extract_fields(image: Image.Image, engine: str = "local_vlm") -> Contact:
    """Extract structured contact fields from a card image using the local VLM."""
    engines = {
        "local_vlm": extract_with_local_vlm,
    }
    if engine not in engines:
        logger.error("Unknown engine requested: %r", engine)
        raise ValueError(f"Unknown engine: {engine!r}. Choose from {list(engines)}.")

    logger.info("Starting extraction with engine=%s", engine)
    return engines[engine](image)
