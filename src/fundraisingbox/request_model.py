from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Anrede(str, Enum):
    MR = "Mr."
    MRS = "Mrs."
    Family = "family"


@dataclass
class CustomField:
    id: str
    name: str
    value: str


@dataclass
class FundraisingBoxRequest:
    first_name: str
    last_name: str
    salutation: Anrede
    title: str | None = None
    birthday: datetime | None = None
    company_id: int | None = None
    company_name: str | None = None
    position: str | None = None
    info: str | None = None
    wants_mailing: bool = False
    wants_no_email: bool = False
    wants_no_call: bool = False
    greeting: str | None = None
    is_company: bool = False
    external_person_id: str | None = None
    fb_custom_fields: list[CustomField] = field(default_factory=list)
