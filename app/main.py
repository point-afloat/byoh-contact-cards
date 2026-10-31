from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import router
from app.api_errors import error_response, register_error_handlers
from app.fundraisingbox.client import FundraisingBoxError
from app.services import Services, install_services


def create_app(services: Services | None = None) -> FastAPI:
    app = FastAPI(title="Contact card importer")
    register_error_handlers(app)
    install_services(app, services)

    @app.exception_handler(FundraisingBoxError)
    async def _fundraisingbox_error(_: Request, exc: FundraisingBoxError) -> JSONResponse:
        return error_response(502, exc.code, str(exc))

    app.include_router(router)
    return app


app = create_app()
