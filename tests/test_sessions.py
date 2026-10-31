import logging

import pytest

from app.api_errors import ApiError
from app.contact import Contact
from app.images import PreparedImage
from app.sessions import SessionStore

IMAGE = PreparedImage(data=b"jpeg", media_type="image/jpeg", width=1, height=1)
CONTACT = Contact(first_name="Anna", last_name="Meier", email="anna@private.example")


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_store(ttl: int = 60, max_sessions: int = 5) -> tuple[SessionStore, FakeClock]:
    clock = FakeClock()
    return SessionStore(ttl_seconds=ttl, max_sessions=max_sessions, clock=clock), clock


def test_create_and_get_round_trip_with_unguessable_ids() -> None:
    store, _ = make_store()
    a = store.create(IMAGE, CONTACT)
    b = store.create(IMAGE, CONTACT)
    assert a.id != b.id and len(a.id) >= 40
    assert store.get(a.id).contact == CONTACT


def test_session_expires_after_ttl_of_inactivity() -> None:
    store, clock = make_store(ttl=60)
    session = store.create(IMAGE, CONTACT)
    clock.now += 61
    with pytest.raises(ApiError) as exc:
        store.get(session.id)
    assert exc.value.code == "session_expired"
    assert exc.value.status_code == 404
    assert len(store) == 0


def test_activity_extends_the_session() -> None:
    store, clock = make_store(ttl=60)
    session = store.create(IMAGE, CONTACT)
    clock.now += 50
    store.get(session.id)
    clock.now += 50
    assert store.get(session.id).id == session.id


def test_unknown_id_reports_expired() -> None:
    store, _ = make_store()
    with pytest.raises(ApiError) as exc:
        store.get("nope")
    assert exc.value.code == "session_expired"


def test_update_contact_replaces_values() -> None:
    store, _ = make_store()
    session = store.create(IMAGE, CONTACT)
    store.update_contact(session.id, Contact(first_name="Berta"))
    assert store.get(session.id).contact == Contact(first_name="Berta")


def test_mark_sent_discards_image_and_contact_but_keeps_the_sent_flag() -> None:
    store, _ = make_store()
    session = store.create(IMAGE, CONTACT)
    store.mark_sent(session.id, "42")
    after = store.get(session.id)
    assert after.sent is True and after.person_id == "42"
    assert after.image is None and after.contact is None


def test_sent_session_cannot_be_edited() -> None:
    store, _ = make_store()
    session = store.create(IMAGE, CONTACT)
    store.mark_sent(session.id, "42")
    with pytest.raises(ApiError) as exc:
        store.update_contact(session.id, Contact(first_name="X"))
    assert exc.value.code == "already_sent"


def test_discard_removes_the_session() -> None:
    store, _ = make_store()
    session = store.create(IMAGE, CONTACT)
    store.discard(session.id)
    with pytest.raises(ApiError):
        store.get(session.id)


def test_session_count_is_capped_but_expired_sessions_free_space() -> None:
    store, clock = make_store(ttl=60, max_sessions=2)
    store.create(IMAGE, CONTACT)
    store.create(IMAGE, CONTACT)
    with pytest.raises(ApiError) as exc:
        store.create(IMAGE, CONTACT)
    assert exc.value.code == "too_many_sessions"
    clock.now += 61
    assert store.create(IMAGE, CONTACT)


def test_card_data_never_appears_in_log_output(caplog: pytest.LogCaptureFixture) -> None:
    store, clock = make_store()
    with caplog.at_level(logging.DEBUG):
        session = store.create(IMAGE, CONTACT)
        store.get(session.id)
        store.update_contact(session.id, CONTACT)
        store.mark_sent(session.id, "42")
        clock.now += 1000
        with pytest.raises(ApiError):
            store.get(session.id)
        repr(session)
    assert "Anna" not in caplog.text and "private.example" not in caplog.text
    assert "Anna" not in repr(session)


def test_repr_of_a_live_session_hides_card_data() -> None:
    store, _ = make_store()
    session = store.create(IMAGE, CONTACT)
    assert "Anna" not in repr(session) and "private.example" not in repr(session)
