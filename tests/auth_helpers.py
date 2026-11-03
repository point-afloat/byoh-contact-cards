"""Shared helpers for tests that need a running app with accounts."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app
from app.models import User
from app.passwords import hash_password
from app.services import Services, build_services
from app.timeutil import Clock, utcnow

ADMIN_EMAIL = "admin@example.org"
ADMIN_PASSWORD = "a very long admin password"
NO_FRONTEND_BUILD = Path("no-frontend-build")
CSRF_HEADER = {"X-Requested-With": "tests"}

SETTINGS: dict[str, Any] = {
    "llm_base_url": "https://llm.example/v1",
    "llm_model": "tiny",
    "llm_api_key": "k",
    "fundraisingbox_apitoken": "fb-secret-token-123",
    "initial_admin_email": ADMIN_EMAIL,
    "initial_admin_password": ADMIN_PASSWORD,
}


class FakeClock:
    """A clock tests can move forward."""

    def __init__(self) -> None:
        self.now = utcnow()

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


def make_services(data_dir: Path, clock: Clock | None = None, **overrides: Any) -> Services:
    settings = load_settings(_env_file=None, data_dir=data_dir, **{**SETTINGS, **overrides})
    return build_services(settings, clock) if clock else build_services(settings)


def web_client(services: Services) -> TestClient:
    """A client over https (the session cookie is Secure) that sends the CSRF header."""
    app = create_app(services, static_dir=NO_FRONTEND_BUILD)
    return TestClient(app, base_url="https://testserver", headers=CSRF_HEADER)


@contextmanager
def running(
    data_dir: Path, clock: Clock | None = None, **overrides: Any
) -> Iterator[tuple[TestClient, Services]]:
    services = make_services(data_dir, clock, **overrides)
    with web_client(services) as client:
        yield client, services


def sign_in(client: TestClient, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> Any:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response


def add_user(
    services: Services,
    email: str,
    password: str | None = "a perfectly fine password",
    role: str = "member",
    active: bool = True,
) -> int:
    """Create a user directly in the database (password None means a pending invitation)."""
    with services.db.session() as db:
        user = User(
            email=email.lower(),
            password_hash=hash_password(password) if password else None,
            role=role,
            is_active=active,
            created_at=services.clock(),
        )
        db.add(user)
        db.flush()
        return user.id
