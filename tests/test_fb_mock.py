"""The in-memory FundraisingBox stand-in (fundraisingbox-mock spec)."""

from pathlib import Path

import respx

from app.contact import Contact
from app.fundraisingbox.client import FundraisingBoxClient
from app.fundraisingbox.mapping import CONTACTPILOT_CUSTOM_FIELD
from app.fundraisingbox.mock import FIRST_ID, MockFundraisingBox
from tests.auth_helpers import SETTINGS, make_services

ANNA = Contact(first_name="Anna", last_name="Meier", company="Acme GmbH", email="a@acme.org")


def test_the_example_companies_are_found_in_any_letter_case() -> None:
    mock = MockFundraisingBox()
    assert [m.name for m in mock.search_companies("acme")] == ["Acme GmbH"]
    assert [m.name for m in mock.search_companies("BEISPIEL")] == ["Beispiel e.V."]
    assert [m.city for m in mock.search_companies("stiftung mus")] == ["München"]
    assert mock.search_companies("nothing like this") == []


def test_a_blank_search_finds_nothing_like_the_live_search() -> None:
    assert MockFundraisingBox().search_companies("   ") == []


def test_the_search_is_limited() -> None:
    mock = MockFundraisingBox()
    for n in range(5):
        mock.create_company(f"Shared Name {n}")
    assert len(mock.search_companies("shared", limit=3)) == 3


def test_a_created_company_is_found_afterwards() -> None:
    mock = MockFundraisingBox()
    created = mock.create_company("Neu & Gut e.V.")
    found = mock.search_companies("neu &")
    assert [(m.id, m.name) for m in found] == [(created.id, "Neu & Gut e.V.")]


def test_every_record_gets_its_own_recognisable_identifier() -> None:
    mock = MockFundraisingBox()
    ids = [
        mock.create_company("One").id,
        mock.create_person(ANNA).id,
        mock.create_person(ANNA).id,
        mock.create_company("Two").id,
    ]
    assert len(set(ids)) == 4 and min(ids) > FIRST_ID  # the built-in companies took the first ones
    assert all(identifier >= FIRST_ID for identifier in ids)


def test_it_uses_the_real_mapping_and_hands_the_payload_back() -> None:
    mock = MockFundraisingBox()
    person = mock.create_person(ANNA, company_id=900001)
    assert person.payload["last_name"] == "Meier" and person.payload["company_id"] == 900001
    assert "Email" not in person.payload.get("info", "")  # the email is a record of its own
    assert person.payload["fb_custom_fields"] == [CONTACTPILOT_CUSTOM_FIELD]
    company = mock.create_company("Neu")
    assert company.payload == {"is_company": True, "company_name": "Neu"}


def test_detail_records_get_ids_and_hand_back_the_payload() -> None:
    mock = MockFundraisingBox()
    person = mock.create_person(ANNA)
    email = mock.add_email(person.id, ANNA)
    phone = mock.add_phone(person.id, "123", mobile=True, is_main=False)
    address = mock.add_address(person.id, Contact(last_name="M", city="Bern", country="Schweiz"))
    website = mock.add_website(person.id, Contact(last_name="M", website="https://a.org"))
    assert len({person.id, email.id, phone.id, address.id, website.id}) == 5
    assert email.payload["fb_person_id"] == person.id and email.payload["email"] == "a@acme.org"
    assert phone.payload["type"] == "other" and address.payload["country"] == "CH"
    assert website.payload["url"] == "https://a.org"


def test_it_never_makes_a_network_request() -> None:
    with respx.mock(assert_all_called=False) as router:  # no routes: any request would fail
        mock = MockFundraisingBox()
        mock.search_companies("acme")
        mock.create_company("X")
        mock.create_person(ANNA)
        assert router.calls.call_count == 0


def test_it_needs_no_token(tmp_path: Path) -> None:
    settings = {**SETTINGS, "fundraisingbox_mode": "mock", "fundraisingbox_apitoken": None}
    services = make_services(tmp_path, **settings)
    assert isinstance(services.fundraisingbox, MockFundraisingBox)
    assert services.fundraisingbox.create_person(ANNA).id >= FIRST_ID


def test_live_is_the_default_and_the_mode_picks_the_implementation(tmp_path: Path) -> None:
    live = make_services(tmp_path / "live")
    assert isinstance(live.fundraisingbox, FundraisingBoxClient)
    mock = make_services(tmp_path / "mock", fundraisingbox_mode="mock")
    assert isinstance(mock.fundraisingbox, MockFundraisingBox)
