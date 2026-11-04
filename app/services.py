"""Wiring of the application services. Built lazily so importing the app never needs
configuration; a configuration problem surfaces as a clear ConfigError on first use."""

import threading
from dataclasses import dataclass

from fastapi import FastAPI, Request

from app.accounts import AccountService
from app.auth import AuthService
from app.config import Settings, get_settings
from app.db import Database
from app.extraction import ExtractionClient
from app.fundraisingbox.client import FundraisingBoxClient
from app.fundraisingbox.gateway import FundraisingBoxGateway
from app.fundraisingbox.mock import MockFundraisingBox
from app.sessions import SessionStore
from app.timeutil import Clock, utcnow


@dataclass
class Services:
    settings: Settings
    db: Database
    auth: AuthService
    accounts: AccountService
    clock: Clock
    store: SessionStore
    extraction: ExtractionClient
    fundraisingbox: FundraisingBoxGateway


def build_services(settings: Settings, clock: Clock = utcnow) -> Services:
    db = Database(settings.data_dir)
    return Services(
        settings=settings,
        db=db,
        auth=AuthService(db, settings, clock),
        accounts=AccountService(db, settings, clock),
        clock=clock,
        store=SessionStore(settings.session_ttl_seconds, settings.session_max_count),
        extraction=ExtractionClient(settings),
        fundraisingbox=(
            MockFundraisingBox()
            if settings.fundraisingbox_mode == "mock"
            else FundraisingBoxClient(settings)
        ),
    )


_lock = threading.Lock()


def install_services(app: FastAPI, services: Services | None = None) -> None:
    app.state.services = services


def ensure_services(app: FastAPI) -> Services:
    """Build the services on first use. Raises ConfigError when configuration is invalid."""
    with _lock:
        if app.state.services is None:
            app.state.services = build_services(get_settings())
        services: Services = app.state.services
        return services


def get_services(request: Request) -> Services:
    return ensure_services(request.app)
