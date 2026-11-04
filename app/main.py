import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app import admin_api, auth_api
from app.api import public_router, router
from app.api_errors import error_response, register_error_handlers
from app.auth import session_cookie_name
from app.body_limit import BodyLimit
from app.config import Settings, get_settings
from app.errors import ConfigError
from app.fundraisingbox.client import FundraisingBoxError
from app.health import prepare_on_startup
from app.services import Services, install_services
from app.spa import default_static_dir, mount_spa

logger = logging.getLogger(__name__)


def upload_limit_for(app: FastAPI) -> int:
    """The configured upload limit, looked up per request because settings load lazily.

    With invalid configuration the default applies, so the size limit still protects the app
    and the usual clear 503 about the configuration is what the caller eventually sees.
    """
    services: Services | None = app.state.services
    if services is not None:
        return services.settings.upload_max_bytes
    try:
        return get_settings().upload_max_bytes
    except ConfigError:
        return int(Settings.model_fields["upload_max_bytes"].default)


def session_cookie_for(app: FastAPI) -> str:
    """The session cookie's name, looked up per request like the upload limit (same fallback)."""
    services: Services | None = app.state.services
    if services is not None:
        return session_cookie_name(services.settings.auth_cookie_secure)
    try:
        return session_cookie_name(get_settings().auth_cookie_secure)
    except ConfigError:
        return session_cookie_name(bool(Settings.model_fields["auth_cookie_secure"].default))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Be loud at startup rather than at the first request. The app keeps running so the
    # platform sees an unhealthy service and the log explains why.
    problems = prepare_on_startup(app)
    for problem in problems:
        logger.error("Startup problem: %s", problem)
    if not problems:
        logger.info("Configuration OK")
    yield


def create_app(services: Services | None = None, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Contact card importer", lifespan=lifespan)
    register_error_handlers(app)
    install_services(app, services)

    @app.middleware("http")
    async def csrf_guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # A cross-site form cannot send a JSON body or a custom header, and a cross-site fetch
        # that does needs a CORS preflight, which this app never allows. So requiring either
        # one on state-changing calls stops cross-site request forgery.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith(
            "/api"
        ):
            json_body = request.headers.get("content-type", "").startswith("application/json")
            if not json_body and "x-requested-with" not in request.headers:
                return error_response(403, "csrf_blocked", "The request was blocked for safety.")
        return await call_next(request)

    # Added after the CSRF guard so it is the outermost layer: an oversized body is refused
    # before the guard, the router, or FastAPI's body parsing sees it.
    app.add_middleware(
        BodyLimit,
        upload_max_bytes=lambda: upload_limit_for(app),
        session_cookie_name=lambda: session_cookie_for(app),
    )

    @app.exception_handler(FundraisingBoxError)
    async def _fundraisingbox_error(_: Request, exc: FundraisingBoxError) -> JSONResponse:
        return error_response(502, exc.code, str(exc))

    app.include_router(public_router)
    app.include_router(auth_api.public)
    app.include_router(auth_api.protected)
    app.include_router(admin_api.router)
    app.include_router(router)
    mount_spa(
        app, static_dir if static_dir is not None else default_static_dir()
    )  # last: catch-all
    return app


app = create_app()
