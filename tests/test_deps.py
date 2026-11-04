"""Which address counts as the client's (spec: client address behind a trusted proxy)."""

from starlette.requests import Request

from app.deps import client_ip

CONNECTION = "10.1.2.3"  # the address of the connection itself (the proxy, when there is one)
PROXY_ADDED = "203.0.113.9"  # what a trusted proxy appends: the real client


def request(forwarded: str | None, connection: str | None = CONNECTION) -> Request:
    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
    scope = {
        "type": "http",
        "headers": headers,
        "client": (connection, 5000) if connection else None,
    }
    return Request(scope)


def test_a_forged_leading_entry_does_not_change_the_counted_address() -> None:
    forged = request(f"1.1.1.1, 2.2.2.2, {PROXY_ADDED}")
    assert client_ip(forged, trusted_proxy=True) == PROXY_ADDED
    assert client_ip(request(f"9.9.9.9, {PROXY_ADDED}"), trusted_proxy=True) == PROXY_ADDED


def test_a_single_entry_is_the_one_the_proxy_added() -> None:
    assert client_ip(request(PROXY_ADDED), trusted_proxy=True) == PROXY_ADDED


def test_whitespace_around_the_entry_is_ignored() -> None:
    assert client_ip(request(f"1.1.1.1 ,   {PROXY_ADDED}  "), trusted_proxy=True) == PROXY_ADDED


def test_a_missing_header_falls_back_to_the_connection_address() -> None:
    assert client_ip(request(None), trusted_proxy=True) == CONNECTION


def test_an_empty_header_falls_back_to_the_connection_address() -> None:
    assert client_ip(request(""), trusted_proxy=True) == CONNECTION
    assert client_ip(request("   "), trusted_proxy=True) == CONNECTION
    assert client_ip(request("1.1.1.1,"), trusted_proxy=True) == CONNECTION  # empty last entry


def test_the_header_is_ignored_when_the_proxy_is_not_trusted() -> None:
    assert client_ip(request(f"1.1.1.1, {PROXY_ADDED}"), trusted_proxy=False) == CONNECTION
    assert client_ip(request(PROXY_ADDED), trusted_proxy=False) == CONNECTION


def test_without_any_connection_information_the_address_is_unknown() -> None:
    assert client_ip(request(None, connection=None), trusted_proxy=False) == "unknown"
    assert client_ip(request("", connection=None), trusted_proxy=True) == "unknown"


def test_an_absurdly_long_entry_is_cut_short() -> None:
    assert len(client_ip(request("a" * 500), trusted_proxy=True)) == 64
