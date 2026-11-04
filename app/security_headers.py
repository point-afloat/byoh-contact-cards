"""Security headers on every response, including the ones other middleware produces.

A pure ASGI middleware, added outermost, so a 413 or a 401 sent before the router ran carries the
same headers as a normal page.
"""

from collections.abc import Callable

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Only the app's own scripts, styles and connections. `blob:` is the card photo preview, made in
# the browser. Inline styles are allowed on elements only (`style-src-attr`), never as <style>
# blocks, and never for scripts.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' blob: data:",
        "style-src 'self'",
        "style-src-attr 'unsafe-inline'",
        "script-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "object-src 'none'",
    ]
)
# 180 days, no includeSubDomains and no preload: a wrong guess about the host is not permanent.
STRICT_TRANSPORT_SECURITY = "max-age=15552000"


class SecurityHeaders:
    def __init__(self, app: ASGIApp, hsts: bool | Callable[[], bool]) -> None:
        self.app = app
        self._hsts = hsts

    def _send_hsts(self) -> bool:
        return self._hsts() if callable(self._hsts) else self._hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        is_api = path == "/api" or path.startswith("/api/")
        hsts = self._send_hsts()

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Frame-Options"] = "DENY"
                if hsts:
                    headers["Strict-Transport-Security"] = STRICT_TRANSPORT_SECURITY
                if is_api:  # names and card data must not sit in a browser or proxy cache
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)
