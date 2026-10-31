"""Card extraction through an OpenAI-compatible chat-completions vision endpoint.

Built for a small, cheap model: one short prompt, a flat all-strings schema,
temperature 0, a small output cap, and at most one retry on malformed JSON.
Card contents and credentials are never logged.
"""

import base64
import json
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.contact import CONTACT_FIELDS, Contact, strict_contact_schema
from app.images import PreparedImage

logger = logging.getLogger(__name__)

MAX_TOKENS = 800
TEMPERATURE = 0
MAX_ATTEMPTS = 2  # first try + at most one retry on malformed JSON
# Words in a 400/422 reply that mean "this endpoint does not support that response_format".
_FORMAT_REJECTED_HINTS = ("response_format", "json_schema", "schema", "structured")
INCOMPLETE_NOTICE = "Some values could not be read reliably, so the result may be incomplete."

SYSTEM_PROMPT = (
    "You read photos of business or contact cards, printed or handwritten. "
    "Reply with one JSON object using exactly these keys, all string values: "
    + ", ".join(CONTACT_FIELDS)
    + ". Copy each value exactly as written on the card. "
    'Use "" for anything that is not on the card or cannot be read. '
    "Never guess or invent values. Put anything else printed on the card in notes. "
    "Reply with the JSON object only."
)
USER_PROMPT = "Extract the contact details from this card."


class _FormatUnsupportedError(Exception):
    """The endpoint rejected the structured-output response_format (internal signal)."""


class ExtractionError(RuntimeError):
    """The model endpoint could not be used. The message is safe to show the user."""

    def __init__(self, message: str, *, code: str = "extraction_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExtractionResult:
    contact: Contact
    incomplete: bool = False
    notice: str | None = None


def _content_text(message_content: Any) -> str:
    """Chat content is usually a string, but some providers return text chunks."""
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        parts = [
            chunk.get("text", "")
            for chunk in message_content
            if isinstance(chunk, Mapping) and isinstance(chunk.get("text"), str)
        ]
        return "".join(parts)
    return ""


def _find_json_object(text: str) -> dict[str, Any] | None:
    """Return the first JSON object found in text, tolerating fences and chatter."""
    decoder = json.JSONDecoder()
    index = text.find("{")
    while index != -1:
        try:
            value, _ = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            index = text.find("{", index + 1)
            continue
        if isinstance(value, dict):
            return value
        index = text.find("{", index + 1)
    return None


def parse_contact(text: str) -> ExtractionResult | None:
    """Parse model output into a Contact, keeping valid fields and dropping the rest.

    Returns None when no usable JSON object with at least one known key is found.
    """
    raw = _find_json_object(text)
    if raw is None or not any(name in raw for name in CONTACT_FIELDS):
        return None

    values: dict[str, str] = {}
    dropped = False
    for name in CONTACT_FIELDS:
        value = raw.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, str | int | float):
            dropped = True
            continue
        values[name] = str(value)
    contact = Contact.model_validate(values)
    return ExtractionResult(
        contact=contact,
        incomplete=dropped,
        notice=INCOMPLETE_NOTICE if dropped else None,
    )


class ExtractionClient:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.llm_timeout)
        # Remembered for the life of the process: a downgrade to json_object sticks.
        self._response_format = settings.llm_response_format

    def extract(self, image: PreparedImage) -> ExtractionResult:
        payload = self._payload(image)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                text = self._call(payload)
            except _FormatUnsupportedError:
                # Not a malformed-answer retry: switch format once and ask again.
                self._response_format = "json_object"
                logger.warning("Endpoint does not support json_schema; using json_object")
                payload = self._payload(image)
                text = self._call(payload)
            result = parse_contact(text)
            if result is not None:
                return result
            logger.warning("Model response was not usable JSON (attempt %d)", attempt)
        return ExtractionResult(contact=Contact(), incomplete=True, notice=INCOMPLETE_NOTICE)

    def _payload(self, image: PreparedImage) -> dict[str, Any]:
        encoded = base64.b64encode(image.data).decode("ascii")
        return {
            "model": self._settings.llm_model,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "response_format": self._response_format_payload(),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{image.media_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
        }

    def _response_format_payload(self) -> dict[str, Any]:
        if self._response_format == "json_schema":
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "contact",
                    "strict": True,
                    "schema": strict_contact_schema(),
                },
            }
        return {"type": "json_object"}

    def _call(self, payload: dict[str, Any]) -> str:
        url = self._settings.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._settings.llm_api_key is not None:
            headers["Authorization"] = f"Bearer {self._settings.llm_api_key.get_secret_value()}"

        started = time.monotonic()
        try:
            response = self._client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise ExtractionError(
                "The model endpoint took too long to answer.", code="extraction_timeout"
            ) from None
        except httpx.RequestError:
            raise ExtractionError(
                "The model endpoint could not be reached.", code="extraction_unreachable"
            ) from None
        logger.info(
            "Model call finished: status=%s seconds=%.1f",
            response.status_code,
            time.monotonic() - started,
        )

        if response.status_code in (401, 403):
            raise ExtractionError(
                "The model endpoint rejected the API key.", code="extraction_unauthorized"
            )
        if response.status_code == 429:
            raise ExtractionError(
                "The model endpoint is busy or the usage limit was reached.",
                code="extraction_rate_limited",
            )
        if (
            response.status_code in (400, 422)
            and self._response_format == "json_schema"
            and _rejects_response_format(response)
        ):
            raise _FormatUnsupportedError
        if response.status_code >= 400:
            raise ExtractionError(
                f"The model endpoint returned an error ({response.status_code}).",
                code="extraction_failed",
            )

        try:
            body = response.json()
            return _content_text(body["choices"][0]["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError):
            return ""


def _rejects_response_format(response: httpx.Response) -> bool:
    """True when a 400/422 reply says the response_format is not supported (body never logged)."""
    text = response.text.lower()
    return any(hint in text for hint in _FORMAT_REJECTED_HINTS)
