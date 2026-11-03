"""FastAPI dependencies that protect routes."""

from typing import Annotated

from fastapi import Depends, Request

from app.api_errors import ApiError
from app.auth import COOKIE_NAME, AuthUser
from app.services import Services, get_services


def client_ip(request: Request, trusted_proxy: bool) -> str:
    """The caller's address. Behind exactly one trusted proxy (Sliplane) that is the last
    X-Forwarded-For entry, the one the proxy itself appended and the client cannot forge."""
    if trusted_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()[:64] or "unknown"
    return request.client.host if request.client else "unknown"


def require_user(request: Request) -> AuthUser:
    """The signed-in user, or a 401 that carries no data."""
    user = get_services(request).auth.authenticate(request.cookies.get(COOKIE_NAME))
    if user is None:
        raise ApiError(401, "not_authenticated", "Please sign in.")
    return user


def require_admin(user: Annotated[AuthUser, Depends(require_user)]) -> AuthUser:
    if not user.is_admin:
        raise ApiError(403, "forbidden", "Only administrators can do this.")
    return user


UserDep = Annotated[AuthUser, Depends(require_user)]
AdminDep = Annotated[AuthUser, Depends(require_admin)]
ServicesDep = Annotated[Services, Depends(get_services)]
