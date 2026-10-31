"""Wiring of the application services. Built lazily so importing the app never needs
configuration; a configuration problem surfaces as a clear ConfigError on first use."""

import threading
from dataclasses import dataclass

from fastapi import FastAPI, Request

from app.config import Settings, get_settings
from app.extraction import ExtractionClient
from app.fundraisingbox.client import FundraisingBoxClient
from app.sessions import SessionStore


@dataclass
class Services:
    settings: Settings
    store: SessionStore
    extraction: ExtractionClient
    fundraisingbox: FundraisingBoxClient


def build_services(settings: Settings) -> Services:
    return Services(
        settings=settings,
        store=SessionStore(settings.session_ttl_seconds, settings.session_max_count),
        extraction=ExtractionClient(settings),
        fundraisingbox=FundraisingBoxClient(settings),
    )


_lock = threading.Lock()


def install_services(app: FastAPI, services: Services | None = None) -> None:
    app.state.services = services


def get_services(request: Request) -> Services:
    app = request.app
    with _lock:
        if app.state.services is None:
            app.state.services = build_services(get_settings())
        services: Services = app.state.services
        return services
