"""The contact schema: single source of truth for API payloads, validation and the
extraction JSON schema. All fields are strings; an empty string means "not found"."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Contact(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    salutation: str = Field(default="", description="Salutation such as Mr., Mrs. or family")
    title: str = Field(default="", description="Academic or professional title, e.g. Dr.")
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    position: str = Field(default="", description="Job title or role")
    email: str = ""
    phone: str = ""
    mobile: str = ""
    street: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = ""
    website: str = ""
    notes: str = Field(default="", description="Anything else printed on the card")


CONTACT_FIELDS: tuple[str, ...] = tuple(Contact.model_fields)


def strict_contact_schema() -> dict[str, Any]:
    """JSON schema for model structured output (strict mode).

    Derived from the Contact model but made strict-friendly: every field is a string, all
    fields are required, no extra keys, and no defaults (strict modes reject optional fields).
    """
    properties = {
        name: {"type": "string", **({"description": d} if (d := field.description) else {})}
        for name, field in Contact.model_fields.items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
