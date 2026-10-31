import pytest

from app.api_errors import ApiError
from app.contact import Contact
from app.fundraisingbox.mapping import (
    CONTACTPILOT_CUSTOM_FIELD,
    INFO_MAX_CHARS,
    build_info,
    company_payload,
    map_salutation,
    person_payload,
)

FULL = Contact(
    salutation="Frau",
    title="Dr.",
    first_name="Anna",
    last_name="Meier",
    company="Acme GmbH",
    position="Head of Fundraising",
    email="anna@acme.org",
    phone="+49 30 1234",
    mobile="+49 170 999",
    street="Hauptstr. 1",
    postal_code="10115",
    city="Berlin",
    country="Germany",
    website="https://acme.org",
    notes="Met at the gala",
)


def test_custom_field_is_exactly_as_in_the_prototype() -> None:
    assert CONTACTPILOT_CUSTOM_FIELD == {"id": "16786", "name": "ContactPilot", "value": "Sync"}
    payload = person_payload(Contact(last_name="Meier"))
    assert payload["fb_custom_fields"] == [{"id": "16786", "name": "ContactPilot", "value": "Sync"}]


def test_company_linked_sends_company_id_and_never_company_name() -> None:
    payload = person_payload(FULL, company_id=42)
    assert payload["company_id"] == 42
    assert "company_name" not in payload
    assert "Company:" not in payload["info"]


def test_no_company_link_keeps_company_in_info_only_when_asked() -> None:
    assert "Company:" not in person_payload(FULL)["info"]
    payload = person_payload(FULL, note_company=True)
    assert "Company: Acme GmbH" in payload["info"]
    assert "company_id" not in payload and "company_name" not in payload


def test_identity_fields_are_mapped() -> None:
    payload = person_payload(FULL, company_id=1)
    assert payload["last_name"] == "Meier" and payload["first_name"] == "Anna"
    assert payload["salutation"] == "Mrs."
    assert payload["title"] == "Dr." and payload["position"] == "Head of Fundraising"
    assert "is_company" not in payload


def test_email_and_phone_are_preserved_in_info() -> None:
    info = person_payload(Contact(last_name="M", email="a@b.org", phone="123"))["info"]
    assert "Email: a@b.org" in info and "Phone: 123" in info


def test_all_channel_data_is_written_as_labelled_lines() -> None:
    assert build_info(FULL).splitlines() == [
        "Phone: +49 30 1234",
        "Mobile: +49 170 999",
        "Email: anna@acme.org",
        "Address: Hauptstr. 1, 10115 Berlin, Germany",
        "Website: https://acme.org",
        "Notes: Met at the gala",
    ]


def test_empty_values_are_left_out_of_the_payload() -> None:
    payload = person_payload(Contact(last_name="Meier"))
    assert set(payload) == {"last_name", "fb_custom_fields"}


def test_over_length_info_is_blocked_with_the_excess_in_the_message() -> None:
    contact = Contact(last_name="M", notes="x" * (INFO_MAX_CHARS + 50))
    with pytest.raises(ApiError) as exc:
        person_payload(contact)
    assert exc.value.code == "info_too_long" and exc.value.status_code == 422
    assert "characters too long" in exc.value.message


def test_info_at_exactly_the_limit_is_allowed() -> None:
    prefix = "Notes: "
    contact = Contact(last_name="M", notes="x" * (INFO_MAX_CHARS - len(prefix)))
    assert len(person_payload(contact)["info"]) == INFO_MAX_CHARS


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Mr.", "Mr."),
        ("Herr", "Mr."),
        ("FRAU", "Mrs."),
        ("Mrs.", "Mrs."),
        ("diverse", "diverse"),
        ("couple", "couple"),
        ("Familie", "family"),
        ("family", "family"),
        ("", None),
        ("Prof", None),
    ],
)
def test_salutations_match_the_api_enum(value: str, expected: str | None) -> None:
    assert map_salutation(value) == expected


def test_company_payload_shape() -> None:
    assert company_payload("Acme GmbH") == {
        "is_company": True,
        "company_name": "Acme GmbH",
        "last_name": "Acme GmbH",
    }
