"""Sign-in, sign-out, the current user and changing one's own password."""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.auth import LEGACY_COOKIE_NAME, session_cookie_name
from app.deps import ServicesDep, UserDep, client_ip, require_user
from app.services import Services

public = APIRouter(prefix="/api/auth")
protected = APIRouter(prefix="/api/auth", dependencies=[Depends(require_user)])


MAX_EMAIL_LENGTH = 320  # the longest address email standards allow
MAX_LOGIN_PASSWORD_LENGTH = 1024  # far beyond any real password, but it bounds the hashing work


class LoginIn(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_LENGTH)
    password: str = Field(max_length=MAX_LOGIN_PASSWORD_LENGTH)


class MeOut(BaseModel):
    id: int
    email: str
    role: str


class TokenIn(BaseModel):
    token: str


class InviteInfoOut(BaseModel):
    email: str
    kind: str  # invite | reset


class AcceptInviteIn(BaseModel):
    token: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


def session_cookie_for(services: Services) -> str:
    return session_cookie_name(services.settings.auth_cookie_secure)


def set_session_cookie(response: Response, services: Services, raw: str) -> None:
    response.set_cookie(
        session_cookie_for(services),
        raw,
        max_age=services.settings.auth_session_days * 86400,
        httponly=True,
        secure=services.settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    if session_cookie_for(services) != LEGACY_COOKIE_NAME:
        # A browser may still hold the cookie an earlier version set under the old name.
        response.delete_cookie(
            LEGACY_COOKIE_NAME, path="/", httponly=True, secure=True, samesite="lax"
        )


def clear_session_cookie(response: Response, services: Services) -> None:
    response.delete_cookie(
        session_cookie_for(services),
        path="/",
        httponly=True,
        secure=services.settings.auth_cookie_secure,
        samesite="lax",
    )


@public.post("/login")
def login(body: LoginIn, request: Request, response: Response, services: ServicesDep) -> MeOut:
    ip = client_ip(request, services.settings.trusted_proxy)
    user, raw = services.auth.login(body.email, body.password, ip)
    set_session_cookie(response, services, raw)
    return MeOut(id=user.id, email=user.email, role=user.role)


@public.post("/invite-info")
def invite_info(body: TokenIn, services: ServicesDep) -> InviteInfoOut:
    """Lets the page tell a valid link from a used or expired one before asking for a password."""
    email, kind = services.auth.invite_info(body.token)
    return InviteInfoOut(email=email, kind=kind)


@public.post("/accept-invite")
def accept_invite(body: AcceptInviteIn, response: Response, services: ServicesDep) -> MeOut:
    user, raw = services.auth.accept_token(body.token, body.password)
    set_session_cookie(response, services, raw)
    return MeOut(id=user.id, email=user.email, role=user.role)


@protected.post("/logout")
def logout(request: Request, response: Response, services: ServicesDep) -> dict[str, str]:
    services.auth.end_session(request.cookies.get(session_cookie_for(services)))
    clear_session_cookie(response, services)
    return {"status": "ok"}


@protected.get("/me")
def me(user: UserDep) -> MeOut:
    return MeOut(id=user.id, email=user.email, role=user.role)


@protected.post("/change-password")
def change_password(
    body: ChangePasswordIn, request: Request, user: UserDep, services: ServicesDep
) -> dict[str, str]:
    services.auth.change_password(
        user.id,
        body.current_password,
        body.new_password,
        client_ip(request, services.settings.trusted_proxy),
        # other sessions end, this one stays
        keep_session_raw=request.cookies.get(session_cookie_for(services)),
    )
    return {"status": "ok"}
