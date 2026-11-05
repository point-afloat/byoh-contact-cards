"""FundraisingBox REST client: company search, company creation and person creation.

The API token is sent as the basic-auth user with password "X". Error messages shown to
users never include the token; response bodies are never logged.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings, require_fundraisingbox_token
from app.contact import Contact
from app.fundraisingbox.mapping import (
    address_payload,
    company_payload,
    email_payload,
    person_payload,
    phone_payload,
    website_payload,
)

logger = logging.getLogger(__name__)

API_URL = "https://api.fundraisingbox.com/v1"
PERSONS_URL = f"{API_URL}/persons.json"
EMAILS_URL = f"{API_URL}/personEmailAddresses.json"
PHONES_URL = f"{API_URL}/personPhones.json"
ADDRESSES_URL = f"{API_URL}/personAddresses.json"
WEBSITES_URL = f"{API_URL}/personWebsites.json"
TIMEOUT_SECONDS = 30
MAX_ERROR_DETAIL = 300


class FundraisingBoxError(RuntimeError):
    """Base class. Messages are safe to show to the user."""

    code = "fundraisingbox_error"


class FundraisingBoxNetworkError(FundraisingBoxError):
    code = "fundraisingbox_unreachable"


class FundraisingBoxApiError(FundraisingBoxError):
    code = "fundraisingbox_rejected"

    def __init__(self, status: int, detail: str = "") -> None:
        message = f"FundraisingBox returned an error ({status})."
        if detail:
            message += f" {detail}"
        super().__init__(message)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class CompanyMatch:
    id: int
    name: str
    city: str | None = None


@dataclass(frozen=True)
class CreatedRecord:
    id: int
    # What was sent. Only the mock fills it (for the demo preview); live leaves it empty.
    payload: dict[str, Any] = field(default_factory=dict)


class FundraisingBoxClient:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def search_companies(self, name: str, limit: int = 10) -> list[CompanyMatch]:
        """Find existing companies whose company name matches."""
        if not name.strip():
            return []
        data = self._call("GET", PERSONS_URL, params={"company": name, "perPage": limit})
        matches: list[CompanyMatch] = []
        for item in data.get("data", []) if isinstance(data, dict) else []:
            company_name = item.get("company_name")
            identifier = item.get("id")
            if not company_name or not isinstance(identifier, int):
                continue
            matches.append(CompanyMatch(id=identifier, name=company_name, city=_first_city(item)))
        return matches

    def create_company(self, name: str) -> CreatedRecord:
        return self._created(self._call("POST", PERSONS_URL, json=company_payload(name)))

    def create_person(
        self, contact: Contact, *, company_id: int | None = None, note_company: bool = False
    ) -> CreatedRecord:
        payload = person_payload(contact, company_id=company_id, note_company=note_company)
        return self._created(self._call("POST", PERSONS_URL, json=payload))

    def add_email(self, owner_id: int, contact: Contact) -> CreatedRecord:
        return self._created(self._call("POST", EMAILS_URL, json=email_payload(owner_id, contact)))

    def add_phone(
        self, owner_id: int, number: str, *, mobile: bool = False, is_main: bool = True
    ) -> CreatedRecord:
        body = phone_payload(owner_id, number, mobile=mobile, is_main=is_main)
        return self._created(self._call("POST", PHONES_URL, json=body))

    def add_address(self, owner_id: int, contact: Contact) -> CreatedRecord:
        body = address_payload(owner_id, contact)
        return self._created(self._call("POST", ADDRESSES_URL, json=body))

    def add_website(self, owner_id: int, contact: Contact) -> CreatedRecord:
        body = website_payload(owner_id, contact)
        return self._created(self._call("POST", WEBSITES_URL, json=body))

    def _call(self, method: str, url: str, **kwargs: Any) -> Any:
        token = require_fundraisingbox_token(self._settings)  # no request without a token
        try:
            response = self._client.request(
                method,
                url,
                auth=(token, "X"),
                headers={"accept": "application/json"},
                **kwargs,
            )
        except httpx.RequestError:
            raise FundraisingBoxNetworkError(
                "FundraisingBox could not be reached. Please try again."
            ) from None
        logger.info("FundraisingBox call: method=%s status=%s", method, response.status_code)
        if response.status_code >= 400:
            raise FundraisingBoxApiError(response.status_code, _error_detail(response))
        try:
            return response.json()
        except ValueError:
            raise FundraisingBoxApiError(
                response.status_code, "The response could not be read."
            ) from None

    @staticmethod
    def _created(body: Any) -> CreatedRecord:
        identifier = body.get("id") if isinstance(body, dict) else None
        if not isinstance(identifier, int):
            raise FundraisingBoxApiError(200, "The response did not contain the new record's id.")
        return CreatedRecord(id=identifier)


def _first_city(item: dict[str, Any]) -> str | None:
    addresses = item.get("fb_person_addresses")
    if isinstance(addresses, list) and addresses and isinstance(addresses[0], dict):
        city = addresses[0].get("city")
        return city if isinstance(city, str) and city else None
    return None


def _error_detail(response: httpx.Response) -> str:
    text = response.text.strip()
    if text in ("", "{}", "[]", "null"):
        return ""
    return text[:MAX_ERROR_DETAIL]
