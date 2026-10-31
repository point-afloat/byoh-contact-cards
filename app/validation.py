"""Review validation rules, shared by saving a draft (reported) and sending (enforced)."""

import re

from app.api_errors import ApiError
from app.contact import Contact

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

IDENTITY_MESSAGE = "Enter a last name or a company."
EMAIL_MESSAGE = "This is not a valid email address."


def validate_contact(contact: Contact) -> dict[str, str]:
    """Return field name -> message for every problem, empty when the contact is valid."""
    errors: dict[str, str] = {}
    if not contact.last_name and not contact.company:
        errors["last_name"] = IDENTITY_MESSAGE
        errors["company"] = IDENTITY_MESSAGE
    if contact.email and not _EMAIL.match(contact.email):
        errors["email"] = EMAIL_MESSAGE
    return errors


def require_valid(contact: Contact) -> None:
    errors = validate_contact(contact)
    if errors:
        raise ApiError(422, "validation_error", "Please fix the highlighted fields.", errors)
