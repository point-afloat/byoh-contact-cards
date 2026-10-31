import pytest

from app.api_errors import ApiError
from app.contact import Contact
from app.validation import require_valid, validate_contact


def test_valid_contact_has_no_errors() -> None:
    assert validate_contact(Contact(last_name="Meier", email="a@b.org")) == {}


def test_company_alone_is_enough() -> None:
    assert validate_contact(Contact(company="Acme")) == {}


def test_missing_identity_flags_both_fields() -> None:
    errors = validate_contact(Contact(first_name="Anna"))
    assert set(errors) == {"last_name", "company"}


@pytest.mark.parametrize("email", ["nope", "a@b", "a b@c.org", "@c.org", "a@.org "])
def test_invalid_emails_are_flagged(email: str) -> None:
    contact = Contact.model_construct(last_name="M", email=email)
    assert "email" in validate_contact(contact)


@pytest.mark.parametrize("email", ["", "a@b.org", "first.last+tag@sub.example.co"])
def test_valid_or_empty_emails_pass(email: str) -> None:
    assert "email" not in validate_contact(Contact(last_name="M", email=email))


def test_require_valid_raises_422_with_field_errors() -> None:
    with pytest.raises(ApiError) as exc:
        require_valid(Contact(email="bad"))
    assert exc.value.status_code == 422 and exc.value.code == "validation_error"
    assert exc.value.errors is not None and {"last_name", "company", "email"} <= set(
        exc.value.errors
    )
