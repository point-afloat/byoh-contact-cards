"""An in-memory stand-in for FundraisingBox, for demos and end-to-end testing.

It makes no network request and needs no token. Records live only in memory, so they disappear
when the server restarts. It builds the very same payloads as the live client, so the field
mapping and its validation (for example the info length) are exercised, and it hands the
payload back so the done screen can show what would have been sent.
"""

import threading
from dataclasses import dataclass

from app.contact import Contact
from app.fundraisingbox.client import CompanyMatch, CreatedRecord
from app.fundraisingbox.mapping import company_payload, person_payload

FIRST_ID = 900001  # recognisably not a real FundraisingBox id

# Obviously fictional.
EXAMPLE_COMPANIES = (
    ("Acme GmbH", "Berlin"),
    ("Beispiel e.V.", "Hamburg"),
    ("Stiftung Muster", "München"),
)


@dataclass(frozen=True)
class _Company:
    id: int
    name: str
    city: str | None


class MockFundraisingBox:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = FIRST_ID
        self._companies: list[_Company] = []
        for name, city in EXAMPLE_COMPANIES:
            self._companies.append(_Company(self._take_id(), name, city))

    def _take_id(self) -> int:
        identifier = self._next_id
        self._next_id += 1
        return identifier

    def search_companies(self, name: str, limit: int = 10) -> list[CompanyMatch]:
        needle = name.strip().lower()
        if not needle:
            return []
        with self._lock:
            found = [c for c in self._companies if needle in c.name.lower()]
        return [CompanyMatch(id=c.id, name=c.name, city=c.city) for c in found[:limit]]

    def create_company(self, name: str) -> CreatedRecord:
        payload = company_payload(name)
        with self._lock:
            identifier = self._take_id()
            self._companies.append(_Company(identifier, name, None))
        return CreatedRecord(id=identifier, payload=payload)

    def create_person(
        self, contact: Contact, *, company_id: int | None = None, note_company: bool = False
    ) -> CreatedRecord:
        payload = person_payload(contact, company_id=company_id, note_company=note_company)
        with self._lock:  # the payload is built first: a refused contact uses up no id
            identifier = self._take_id()
        return CreatedRecord(id=identifier, payload=payload)
