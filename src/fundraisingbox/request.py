import json
import os
from dataclasses import asdict
from typing import Any

import httpx
from dotenv import load_dotenv

from fundraisingbox.request_model import Anrede, CustomField, FundraisingBoxRequest

load_dotenv()

FUNDRAISINGBOX_APITOKEN = os.getenv("FUNDRAISINGBOX_APITOKEN")
FUNDRAISINGBOX_URL: str = "https://api.fundraisingbox.com/v1/persons.json"
FUNDRAISINGBOX_HEADERS: dict = {
    "accept": "application/json",
}
CONTACTPILOT_CUSTOM_FIELD_ID: str = "16786"
CONTACTPILOT_CUSTOM_FIELD_NAME: str = "ContactPilot"


def _fundraisingbox_call(method: str, **kwargs: Any) -> dict:
    if not FUNDRAISINGBOX_APITOKEN:
        raise RuntimeError("Token is not set")
    try:
        response = httpx.request(
            method,
            FUNDRAISINGBOX_URL,
            auth=(FUNDRAISINGBOX_APITOKEN, "X"),
            headers=FUNDRAISINGBOX_HEADERS,
            timeout=30,
            **kwargs,
        )
        response.raise_for_status()
    except httpx.RequestError as e:
        raise RuntimeError(f"Could not reach FundraisingBox: {e}") from e
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"FundraisingBox returned {e.response.status_code}: {e.response.text}"
        ) from e

    return response.json()


def fundraisingbox_request(payload: dict) -> dict:
    return _fundraisingbox_call("POST", json=payload)


def search_companies(name: str, limit: int = 10) -> list[dict]:
    """Search existing FundraisingBox persons whose company name matches.

    This account models donors as companies (existing records have no
    first_name/last_name at all, only company_name) — matching against an
    existing company via company_id, rather than creating a new person with
    identity fields, is what avoids the "not_editable" error on those fields.
    """
    if not name.strip():
        return []
    result = _fundraisingbox_call(
        "GET", params={"company": name, "perPage": limit}
    )
    return result.get("data", [])


if __name__ == "__main__":
    custom_field = CustomField(
        id=CONTACTPILOT_CUSTOM_FIELD_ID,
        name=CONTACTPILOT_CUSTOM_FIELD_NAME,
        value="test",
    )
    request = FundraisingBoxRequest(
        first_name="test",
        last_name="test",
        salutation=Anrede.Family,
        fb_custom_fields=[custom_field],
    )

    print(json.dumps(asdict(request)))
    print(FUNDRAISINGBOX_HEADERS)

    fundraisingbox_request(asdict(request))
