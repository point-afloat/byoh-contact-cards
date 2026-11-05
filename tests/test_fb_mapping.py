import pytest

from app.contact import Contact
from app.fundraisingbox.mapping import (
    CONTACTPILOT_CUSTOM_FIELD,
    INFO_MAX_CHARS,
    LIMITS,
    address_payload,
    build_info,
    company_payload,
    email_payload,
    has_address,
    limit_errors,
    map_salutation,
    person_payload,
    phone_payload,
    website_payload,
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


def test_custom_field_is_as_the_api_documents_it() -> None:
    assert CONTACTPILOT_CUSTOM_FIELD == {"id": 16786, "value": "Sync"}
    payload = person_payload(Contact(last_name="Meier"))
    assert payload["fb_custom_fields"] == [{"id": 16786, "value": "Sync"}]


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


def test_contact_details_are_not_written_into_info() -> None:
    info = build_info(FULL, note_company=True)
    assert info.splitlines() == ["Company: Acme GmbH", "Notes: Met at the gala"]
    for word in ("Email", "Phone", "Mobile", "Address", "Website", "anna@acme.org"):
        assert word not in info


def test_an_unknown_country_text_is_kept_in_info() -> None:
    assert "Country: Atlantis" in build_info(Contact(last_name="M", country="Atlantis"))
    assert build_info(Contact(last_name="M", country="Deutschland")) == ""


def test_detail_records_use_the_documented_fields() -> None:
    assert email_payload(7, FULL) == {
        "fb_person_id": 7,
        "email": "anna@acme.org",
        "type": "work",
        "is_main": True,
    }
    assert phone_payload(7, "123") == {
        "fb_person_id": 7,
        "phone": "123",
        "type": "work",
        "is_main": True,
    }
    mobile = phone_payload(7, "170", mobile=True, is_main=False)
    assert mobile["type"] == "other" and mobile["is_main"] is False
    assert address_payload(7, FULL) == {
        "fb_person_id": 7,
        "type": "work",
        "is_main": True,
        "address": "Hauptstr. 1",
        "post_code": "10115",
        "city": "Berlin",
        "country": "DE",
    }
    assert website_payload(7, FULL) == {
        "fb_person_id": 7,
        "url": "https://acme.org",
        "type": "work",
        "website_type": "homepage",
    }
    assert "is_main" not in website_payload(7, FULL)  # the live API rejects it


def test_an_address_without_a_known_country_has_no_country() -> None:
    body = address_payload(7, Contact(last_name="M", city="Bern", country="Atlantis"))
    assert "country" not in body and body["city"] == "Bern"
    assert has_address(Contact(last_name="M", country="Atlantis")) is False
    assert has_address(Contact(last_name="M", country="AT")) is True


def test_empty_values_are_left_out_of_the_payload() -> None:
    payload = person_payload(Contact(last_name="Meier"))
    assert set(payload) == {"last_name", "fb_custom_fields"}


def test_info_over_the_limit_is_reported_under_notes() -> None:
    contact = Contact(last_name="M", notes="x" * (INFO_MAX_CHARS + 50))
    errors = limit_errors(contact)
    assert "characters too long" in errors["notes"]


def test_info_at_exactly_the_limit_is_allowed() -> None:
    prefix = "Notes: "
    contact = Contact(last_name="M", notes="x" * (INFO_MAX_CHARS - len(prefix)))
    assert len(person_payload(contact)["info"]) == INFO_MAX_CHARS
    assert limit_errors(contact) == {}


@pytest.mark.parametrize("field", list(LIMITS))
def test_every_documented_limit_passes_at_its_length_and_fails_one_over(field: str) -> None:
    limit = LIMITS[field]
    assert field not in limit_errors(Contact(**{field: "x" * limit}))
    assert field in limit_errors(Contact(**{field: "x" * (limit + 1)}))


def test_every_problem_is_reported_at_once() -> None:
    errors = limit_errors(Contact(last_name="x" * 101, phone="1" * 51))
    assert set(errors) == {"last_name", "phone"}


def test_a_valid_contact_passes() -> None:
    assert limit_errors(FULL, note_company=True) == {}


def test_a_long_company_name_is_cut_for_the_required_last_name_only() -> None:
    body = company_payload("A" * 150)
    assert len(body["last_name"]) == 100 and body["company_name"] == "A" * 150


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
