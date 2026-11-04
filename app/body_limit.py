"""Refuse oversized request bodies before they are read or parsed, whoever sends them.

FastAPI reads and parses a request body *before* it runs the dependency that checks the login,
so a route-level check cannot stop an anonymous caller from making the server accept a huge
upload. This pure ASGI middleware sits in front of everything:

* a declared Content-Length over the limit is refused without reading a byte;
* a card upload that carries no session cookie at all is refused unread (401);
* a body without a usable length (chunked) is counted as it arrives and cut off at the limit.

FastAPI turns any error raised while it reads a body into a generic 400, so an overflow cannot be
reported by raising from `receive`. Instead the 413 is sent here, the app is told the client went
away, and whatever the app tries to send afterwards is dropped.
"""

from collections.abc import Callable

from starlette.requests import cookie_parser
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

JSON_LIMIT_BYTES = 64 * 1024  # every route except the card upload takes small JSON
ENVELOPE_ALLOWANCE_BYTES = 64 * 1024  # multipart boundaries and headers around the image
UPLOAD_PATH = "/api/sessions"


def _refusal(status: int, code: str, text: str) -> JSONResponse:
    # "Connection: close" because the unread body may still be on the wire.
    return JSONResponse(
        {"code": code, "message": text}, status_code=status, headers={"Connection": "close"}
    )


def _content_length(scope: Scope) -> bytes | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            return bytes(value).strip()
    return None


def _has_cookie(scope: Scope, name: str) -> bool:
    """Whether the request carries a non-empty cookie with this name (its value is not checked)."""
    for header, value in scope["headers"]:
        if header == b"cookie" and cookie_parser(bytes(value).decode("latin-1")).get(name):
            return True
    return False


class BodyLimit:
    def __init__(
        self,
        app: ASGIApp,
        upload_max_bytes: int | Callable[[], int],
        session_cookie_name: str | Callable[[], str] | None = None,
    ) -> None:
        """The upload limit and the cookie name may be callables, looked up for each request.

        With a `session_cookie_name`, a card upload without that cookie is refused unread.
        """
        self.app = app
        self._upload_max_bytes = upload_max_bytes
        self._session_cookie_name = session_cookie_name

    def _upload_limit(self) -> int:
        value = self._upload_max_bytes
        maximum = value() if callable(value) else value
        return maximum + ENVELOPE_ALLOWANCE_BYTES

    def _cookie_name(self) -> str | None:
        name = self._session_cookie_name
        return name() if callable(name) else name

    @staticmethod
    def _is_upload(scope: Scope) -> bool:
        return bool(scope["method"] == "POST" and scope["path"] == UPLOAD_PATH)

    def _limit_for(self, scope: Scope) -> tuple[int, str, str]:
        if self._is_upload(scope):
            return self._upload_limit(), "file_too_large", "The file is too large."
        return JSON_LIMIT_BYTES, "request_too_large", "The request is too large."

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit, code, text = self._limit_for(scope)

        declared = _content_length(scope)
        if declared is not None:
            if not declared.isdigit():
                response = _refusal(400, "invalid_content_length", "The request is invalid.")
                await response(scope, receive, send)
                return
            if int(declared) > limit:
                await _refusal(413, code, text)(scope, receive, send)
                return

        cookie_name = self._cookie_name() if self._is_upload(scope) else None
        if cookie_name is not None and not _has_cookie(scope, cookie_name):
            # The same answer the usual sign-in check gives, without reading the body first.
            await _refusal(401, "not_authenticated", "Please sign in.")(scope, receive, send)
            return

        seen = 0
        exceeded = False
        refusal_sent = False
        response_started = False

        async def counting_receive() -> Message:
            nonlocal seen, exceeded, refusal_sent
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    exceeded = True
                    if not response_started:
                        refusal_sent = True
                        await _refusal(413, code, text)(scope, receive, send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if refusal_sent:
                return  # the client already has its answer
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not refusal_sent:
                raise
            # The app failed on a body that was cut off. The client has its 413 already.
