from app.contact import CONTACT_FIELDS, Contact

SPEC_FIELDS = {
    "salutation", "title", "first_name", "last_name", "company", "position", "email",
    "phone", "mobile", "street", "postal_code", "city", "country", "website", "notes",
}  # fmt: skip


def test_all_fields_default_to_empty_strings() -> None:
    contact = Contact()
    assert all(getattr(contact, name) == "" for name in CONTACT_FIELDS)


def test_fields_match_the_spec() -> None:
    assert set(CONTACT_FIELDS) == SPEC_FIELDS


def test_json_schema_is_flat_with_string_properties() -> None:
    schema = Contact.model_json_schema()
    assert set(schema["properties"]) == SPEC_FIELDS
    assert all(p["type"] == "string" for p in schema["properties"].values())
    assert "required" not in schema


def test_unknown_keys_are_ignored_and_whitespace_trimmed() -> None:
    contact = Contact.model_validate({"first_name": "  Anna ", "nonsense": 1})
    assert contact.first_name == "Anna"
    assert not hasattr(contact, "nonsense")
