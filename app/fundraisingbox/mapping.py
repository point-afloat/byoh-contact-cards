"""Mapping a reviewed Contact to FundraisingBox payloads.

Email, phone, mobile, address and website have no person fields in the FundraisingBox
API, so they are written as labelled lines into the person's `info` text in the same
create call, as the prototype does. `company_name` is never sent with a person:
linking happens through `company_id`, which avoids the `not_editable` error.
"""

from typing import Any

from app.api_errors import ApiError
from app.contact import Contact

INFO_MAX_CHARS = 1000

CONTACTPILOT_CUSTOM_FIELD: dict[str, str] = {
    "id": "16786",
    "name": "ContactPilot",
    "value": "Sync",
}

SALUTATIONS = {"Mr.", "Mrs.", "diverse", "couple", "family"}
_SALUTATION_ALIASES = {
    "mr": "Mr.",
    "mr.": "Mr.",
    "herr": "Mr.",
    "mrs": "Mrs.",
    "mrs.": "Mrs.",
    "ms": "Mrs.",
    "ms.": "Mrs.",
    "frau": "Mrs.",
    "diverse": "diverse",
    "divers": "diverse",
    "couple": "couple",
    "ehepaar": "couple",
    "family": "family",
    "familie": "family",
}


def map_salutation(value: str) -> str | None:
    """Return a salutation the API accepts, or None when it is empty or unknown."""
    return _SALUTATION_ALIASES.get(value.strip().lower())


def build_info(contact: Contact, *, note_company: bool = False) -> str:
    """Labelled info lines. The company is noted only when it is not linked or created."""
    lines: list[str] = []
    if note_company and contact.company:
        lines.append(f"Company: {contact.company}")
    if contact.phone:
        lines.append(f"Phone: {contact.phone}")
    if contact.mobile:
        lines.append(f"Mobile: {contact.mobile}")
    if contact.email:
        lines.append(f"Email: {contact.email}")
    city_line = " ".join(part for part in (contact.postal_code, contact.city) if part)
    address = ", ".join(part for part in (contact.street, city_line, contact.country) if part)
    if address:
        lines.append(f"Address: {address}")
    if contact.website:
        lines.append(f"Website: {contact.website}")
    if contact.notes:
        lines.append(f"Notes: {contact.notes}")
    return "\n".join(lines)


def person_payload(
    contact: Contact, *, company_id: int | None = None, note_company: bool = False
) -> dict[str, Any]:
    """Build the POST /persons.json body. Raises ApiError when `info` would be too long."""
    info = build_info(contact, note_company=note_company and company_id is None)
    if len(info) > INFO_MAX_CHARS:
        excess = len(info) - INFO_MAX_CHARS
        raise ApiError(
            422,
            "info_too_long",
            f"The contact details are {excess} characters too long for FundraisingBox. "
            "Please shorten them (for example the notes).",
        )

    payload: dict[str, Any] = {"last_name": contact.last_name}
    optional: dict[str, Any] = {
        "first_name": contact.first_name,
        "salutation": map_salutation(contact.salutation),
        "title": contact.title,
        "position": contact.position,
        "company_id": company_id,
        "info": info,
    }
    payload.update({key: value for key, value in optional.items() if value not in ("", None)})
    payload["fb_custom_fields"] = [dict(CONTACTPILOT_CUSTOM_FIELD)]
    return payload


def company_payload(name: str) -> dict[str, Any]:
    """Body for creating a company record.

    UNVERIFIED against a live account (task 3.4): the API requires `last_name` on every
    record and documents `company_name` only for `is_company=true`.
    """
    return {"is_company": True, "company_name": name, "last_name": name}
