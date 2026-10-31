"""Uniform `{code, message}` error bodies for the JSON API."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import ConfigError


class ApiError(Exception):
    """An error the API reports to the client as `{code, message}`."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        errors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.errors = errors


def error_response(
    status_code: int, code: str, message: str, errors: dict[str, str] | None = None
) -> JSONResponse:
    content: dict[str, object] = {"code": code, "message": message}
    if errors:
        content["errors"] = errors  # field name -> message
    return JSONResponse(status_code=status_code, content=content)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.errors)

    @app.exception_handler(ConfigError)
    async def _config_error(_: Request, exc: ConfigError) -> JSONResponse:
        return error_response(503, exc.code, str(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error_response(exc.status_code, f"http_{exc.status_code}", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted(
            {".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]) for e in exc.errors()}
        )
        return error_response(422, "validation_error", "Invalid request: " + ", ".join(fields))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, __: Exception) -> JSONResponse:
        # Never leak internals or card data in the body.
        return error_response(500, "internal_error", "Something went wrong on the server.")
