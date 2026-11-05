"""What the rest of the app needs from FundraisingBox: the live client or the in-memory mock."""

from typing import Protocol

from app.contact import Contact
from app.fundraisingbox.client import CompanyMatch, CreatedRecord


class FundraisingBoxGateway(Protocol):
    def search_companies(self, name: str, limit: int = 10) -> list[CompanyMatch]: ...

    def create_company(self, name: str) -> CreatedRecord: ...

    def create_person(
        self, contact: Contact, *, company_id: int | None = None, note_company: bool = False
    ) -> CreatedRecord: ...

    def add_email(self, owner_id: int, contact: Contact) -> CreatedRecord: ...

    def add_phone(
        self, owner_id: int, number: str, *, mobile: bool = False, is_main: bool = True
    ) -> CreatedRecord: ...

    def add_address(self, owner_id: int, contact: Contact) -> CreatedRecord: ...

    def add_website(self, owner_id: int, contact: Contact) -> CreatedRecord: ...
