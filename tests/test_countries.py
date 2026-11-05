import pytest

from app.fundraisingbox.countries import country_code


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Deutschland", "DE"),
        ("germany", "DE"),
        ("AT", "AT"),
        (" Österreich ", "AT"),
        ("Schweiz", "CH"),
        ("at", "AT"),
        ("Atlantis", None),
        ("", None),
    ],
)
def test_country_names_become_codes(text: str, code: str | None) -> None:
    assert country_code(text) == code
