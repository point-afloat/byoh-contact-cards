"""Mapping a reviewed Contact to FundraisingBox records.

A contact becomes a person record plus separate email, phone, address and website records,
each linked to the person by `fb_person_id`. `info` keeps only what has no field of its own:
the notes, the company name when it is not linked, and a country text that is not a country.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.contact import Contact
from app.fundraisingbox.countries import country_code

INFO_MAX_CHARS = 1000

# Documented maximum lengths: field name on the contact -> limit.
LIMITS: dict[str, int] = {
    "last_name": 100,
    "first_name": 100,
    "title": 50,
    "position": 200,
    "company": 1000,
    "email": 100,
    "phone": 50,
    "mobile": 50,
    "street": 300,
    "postal_code": 100,
    "city": 100,
    "website": 1000,
}

WORK = "work"
MOBILE_TYPE = "other"  # the documented create enum has home, work, other only
WEBSITE_TYPE = "homepage"

CONTACTPILOT_CUSTOM_FIELD: dict[str, Any] = {"id": 16786, "value": "Sync"}

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


class Preferences(BaseModel):
    """Consent the reviewer ticked. Never read from the card; unticked means no claim."""

    model_config = ConfigDict(extra="forbid")

    newsletter: bool = False
    email: bool = False
    phone: bool = False
    post: bool = False


def preference_flags(preferences: Preferences | None) -> dict[str, bool]:
    """FundraisingBox flags for the ticked options only (the others keep FundraisingBox's default).

    Ticked contact options clear the matching "do not contact" flag. Direction of the three
    wants_no_* flags and the meaning of wants_newsletter are read from sparse documentation and
    are checked on the first live send.
    """
    if preferences is None:
        return {}
    flags: dict[str, bool] = {}
    if preferences.newsletter:
        flags["wants_newsletter"] = True
    if preferences.email:
        flags["wants_no_email"] = False
    if preferences.phone:
        flags["wants_no_call"] = False
    if preferences.post:
        flags["wants_no_post"] = False
    return flags


def has_address(contact: Contact) -> bool:
    return bool(
        contact.street or contact.postal_code or contact.city or country_code(contact.country)
    )


def build_info(contact: Contact, *, note_company: bool = False) -> str:
    """Notes, the unlinked company and a country text that could not be converted."""
    lines: list[str] = []
    if note_company and contact.company:
        lines.append(f"Company: {contact.company}")
    if contact.country and country_code(contact.country) is None:
        lines.append(f"Country: {contact.country}")
    if contact.notes:
        lines.append(f"Notes: {contact.notes}")
    return "\n".join(lines)


def limit_errors(contact: Contact, *, note_company: bool = False) -> dict[str, str]:
    """Field name -> message for every documented limit the contact exceeds."""
    errors: dict[str, str] = {}
    for name, limit in LIMITS.items():
        value = getattr(contact, name)
        if len(value) > limit:
            errors[name] = f"Too long for FundraisingBox: at most {limit} characters."
    info = build_info(contact, note_company=note_company)
    if len(info) > INFO_MAX_CHARS:
        excess = len(info) - INFO_MAX_CHARS
        errors["notes"] = (
            f"The notes are {excess} characters too long for FundraisingBox. Please shorten them."
        )
    return errors


def person_payload(
    contact: Contact,
    *,
    company_id: int | None = None,
    note_company: bool = False,
    preferences: Preferences | None = None,
) -> dict[str, Any]:
    """Build the POST /persons.json body (documented person fields only)."""
    payload: dict[str, Any] = {"last_name": contact.last_name}
    optional: dict[str, Any] = {
        "first_name": contact.first_name,
        "salutation": map_salutation(contact.salutation),
        "title": contact.title,
        "position": contact.position,
        "company_id": company_id,
        "info": build_info(contact, note_company=note_company and company_id is None),
    }
    payload.update({key: value for key, value in optional.items() if value not in ("", None)})
    payload.update(preference_flags(preferences))
    payload["fb_custom_fields"] = [dict(CONTACTPILOT_CUSTOM_FIELD)]
    return payload


def company_payload(name: str, preferences: Preferences | None = None) -> dict[str, Any]:
    """Body for creating a company record.

    The documented `last_name` applies only when `is_company` is false, and the live API
    rejects it for a company as `not_editable`, so a company carries `company_name` only.
    The name limit is checked locally (see LIMITS["company"]).
    """
    return {"is_company": True, "company_name": name, **preference_flags(preferences)}


def email_payload(owner_id: int, contact: Contact) -> dict[str, Any]:
    return {"fb_person_id": owner_id, "email": contact.email, "type": WORK, "is_main": True}


def phone_payload(
    owner_id: int, number: str, *, mobile: bool = False, is_main: bool = True
) -> dict[str, Any]:
    return {
        "fb_person_id": owner_id,
        "phone": number,
        "type": MOBILE_TYPE if mobile else WORK,
        "is_main": is_main,
    }


def address_payload(owner_id: int, contact: Contact) -> dict[str, Any]:
    body: dict[str, Any] = {"fb_person_id": owner_id, "type": WORK, "is_main": True}
    optional = {
        "address": contact.street,
        "post_code": contact.postal_code,
        "city": contact.city,
        "country": country_code(contact.country),
    }
    body.update({key: value for key, value in optional.items() if value})
    return body


def website_payload(owner_id: int, contact: Contact) -> dict[str, Any]:
    return {
        "fb_person_id": owner_id,
        "url": contact.website,
        "type": WORK,
        "website_type": WEBSITE_TYPE,
    }  # personWebsites has no is_main field: the live API rejects it as unknown
