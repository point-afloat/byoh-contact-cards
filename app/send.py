"""Sending a reviewed contact to FundraisingBox.

Order of work: check everything that can fail locally first, then create the company if the
user asked for it, then the person, then one request per detail (email, phone, mobile,
address, website) with the new id. What was created is remembered on the session, so a retry
after a failure part way only sends what is missing and never creates a second person.
"""

from collections.abc import Callable
from typing import Any, Literal, Self

from pydantic import BaseModel, model_validator

from app.api_errors import ApiError
from app.contact import Contact
from app.fundraisingbox.client import CreatedRecord, FundraisingBoxError
from app.fundraisingbox.mapping import Preferences, has_address, limit_errors
from app.services import Services
from app.sessions import Session
from app.validation import validate_contact


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
    preferences: Preferences = Preferences()


def send_session(services: Services, session_id: str, request: SendRequest) -> Session:
    session = services.store.get(session_id)
    if not session.send_lock.acquire(blocking=False):
        raise ApiError(409, "send_in_progress", "This contact is already being sent.")
    try:
        if session.sent:
            raise ApiError(409, "already_sent", "This contact was already sent.")
        services.store.update_contact(session_id, request.contact)
        contact = request.contact
        note_company = request.company.mode == "none"
        errors = validate_contact(contact)
        errors.update(limit_errors(contact, note_company=note_company))
        if errors:
            raise ApiError(422, "validation_error", "Please fix the highlighted fields.", errors)

        if not contact.last_name:
            return _send_company_only(
                services, session, contact, request.company, request.preferences
            )
        return _send_person(services, session, contact, request.company, request.preferences)
    finally:
        session.send_lock.release()


def _send_company_only(
    services: Services,
    session: Session,
    contact: Contact,
    choice: CompanyChoice,
    preferences: Preferences,
) -> Session:
    if choice.mode != "create":
        raise ApiError(
            422,
            "nothing_to_create",
            "Without a last name only a new company can be created. "
            "Choose to create the company, or add a last name.",
        )
    company_id = _create_company_once(services, session, contact.company, preferences)
    _send_details(services, session, company_id, contact)
    payload = session.created_company_payload
    return services.store.mark_sent(
        session.id,
        str(company_id),
        "company",
        demo_payload=_demo_payload("company", payload, session.finished_steps),
    )


def _send_person(
    services: Services,
    session: Session,
    contact: Contact,
    choice: CompanyChoice,
    preferences: Preferences,
) -> Session:
    note_company = choice.mode == "none"
    if session.created_person is None:
        company_id: int | None = None
        if choice.mode == "link":
            company_id = choice.id
        elif choice.mode == "create":
            if not contact.company:
                raise ApiError(
                    422, "company_missing", "Enter a company name to create the company."
                )
            company_id = _create_company_once(services, session, contact.company)
        created = services.fundraisingbox.create_person(
            contact, company_id=company_id, note_company=note_company, preferences=preferences
        )
        session.created_person = (created.id, created.payload)

    person_id, person_payload = session.created_person
    _send_details(services, session, person_id, contact)
    return services.store.mark_sent(
        session.id,
        str(person_id),
        "person",
        demo_payload=_demo_payload("person", person_payload, session.finished_steps),
    )


def _send_details(services: Services, session: Session, owner_id: int, contact: Contact) -> None:
    """Run the detail steps that are not finished yet; stop at the first failure."""
    gateway = services.fundraisingbox
    steps: list[tuple[str, Callable[[], CreatedRecord]]] = []
    if contact.email:
        steps.append(("email", lambda: gateway.add_email(owner_id, contact)))
    if contact.phone:
        steps.append(("phone", lambda: gateway.add_phone(owner_id, contact.phone)))
    if contact.mobile:
        steps.append(
            (
                "mobile",
                lambda: gateway.add_phone(
                    owner_id, contact.mobile, mobile=True, is_main=not contact.phone
                ),
            )
        )
    if has_address(contact):
        steps.append(("address", lambda: gateway.add_address(owner_id, contact)))
    if contact.website:
        steps.append(("website", lambda: gateway.add_website(owner_id, contact)))

    for index, (name, run) in enumerate(steps):
        if name in session.finished_steps:
            continue
        try:
            session.finished_steps[name] = run().payload
        except FundraisingBoxError as error:
            missing = [n for n, _ in steps[index:] if n not in session.finished_steps]
            raise ApiError(
                502,
                "partly_sent",
                "The contact was created in FundraisingBox, but these details are missing: "
                f"{', '.join(missing)}. {error} Your entries are kept: correct them if needed "
                "and send again to add only what is missing. Changes to the name, the company or "
                "the newsletter and contact options are not applied to the record that "
                "already exists.",
            ) from None


_STEP_LISTS = {"email": "emails", "phone": "phones", "mobile": "phones", "address": "addresses"}


def _demo_payload(
    kind: str, record: dict[str, Any] | None, steps: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    """Mock mode preview: the main record plus a list per kind of detail record."""
    if not record:
        return None
    preview: dict[str, Any] = {kind: record}
    for name, payload in steps.items():
        preview.setdefault(_STEP_LISTS.get(name, "websites"), []).append(payload)
    return preview


def _create_company_once(
    services: Services, session: Session, name: str, preferences: Preferences | None = None
) -> int:
    if session.created_company is not None and session.created_company[0] == name:
        return session.created_company[1]
    created = services.fundraisingbox.create_company(name, preferences)
    session.created_company = (name, created.id)
    session.created_company_payload = created.payload
    return created.id
