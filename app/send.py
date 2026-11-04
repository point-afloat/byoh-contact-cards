"""Sending a reviewed contact to FundraisingBox.

Order of work: validate and build everything that can fail locally first, then create the
company if the user asked for it, then the person. A company created by an attempt that
later failed is remembered on the session, so a retry never creates it twice.
"""

from typing import Literal, Self

from pydantic import BaseModel, model_validator

from app.api_errors import ApiError
from app.contact import Contact
from app.fundraisingbox.mapping import person_payload
from app.services import Services
from app.sessions import Session
from app.validation import require_valid


class CompanyChoice(BaseModel):
    mode: Literal["none", "link", "create"] = "none"
    id: int | None = None

    @model_validator(mode="after")
    def _link_needs_an_id(self) -> Self:
        if self.mode == "link" and self.id is None:
            raise ValueError("id is required when mode is 'link'")
        return self


class SendRequest(BaseModel):
    contact: Contact
    company: CompanyChoice = CompanyChoice()


def send_session(services: Services, session_id: str, request: SendRequest) -> Session:
    session = services.store.get(session_id)
    if not session.send_lock.acquire(blocking=False):
        raise ApiError(409, "send_in_progress", "This contact is already being sent.")
    try:
        if session.sent:
            raise ApiError(409, "already_sent", "This contact was already sent.")
        services.store.update_contact(session_id, request.contact)
        contact = request.contact
        require_valid(contact)

        if not contact.last_name:
            return _send_company_only(services, session, contact, request.company)
        return _send_person(services, session, contact, request.company)
    finally:
        session.send_lock.release()


def _send_company_only(
    services: Services, session: Session, contact: Contact, choice: CompanyChoice
) -> Session:
    if choice.mode != "create":
        raise ApiError(
            422,
            "nothing_to_create",
            "Without a last name only a new company can be created. "
            "Choose to create the company, or add a last name.",
        )
    company_id = _create_company_once(services, session, contact.company)
    return services.store.mark_sent(
        session.id, str(company_id), "company", demo_payload=session.created_company_payload
    )


def _send_person(
    services: Services, session: Session, contact: Contact, choice: CompanyChoice
) -> Session:
    note_company = choice.mode == "none"
    # Fail locally (for example an over-long info text) before anything is created.
    person_payload(contact, company_id=choice.id, note_company=note_company)

    company_id: int | None = None
    if choice.mode == "link":
        company_id = choice.id
    elif choice.mode == "create":
        if not contact.company:
            raise ApiError(422, "company_missing", "Enter a company name to create the company.")
        company_id = _create_company_once(services, session, contact.company)

    created = services.fundraisingbox.create_person(
        contact, company_id=company_id, note_company=note_company
    )
    return services.store.mark_sent(
        session.id, str(created.id), "person", demo_payload=created.payload
    )


def _create_company_once(services: Services, session: Session, name: str) -> int:
    if session.created_company is not None and session.created_company[0] == name:
        return session.created_company[1]
    created = services.fundraisingbox.create_company(name)
    session.created_company = (name, created.id)
    session.created_company_payload = created.payload
    return created.id
