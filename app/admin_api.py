"""User management for administrators. Every route here requires the admin role."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.accounts import IssuedInvite, UserView
from app.deps import ServicesDep, require_admin

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    status: str  # active | inactive | invited
    created_at: datetime
    last_sign_in_at: datetime | None
    invite_expires_at: datetime | None


class InviteIn(BaseModel):
    email: str
    role: str = "member"


class UserPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class InviteOut(BaseModel):
    user: UserOut
    token: str  # shown once; only its hash is stored
    invite_path: str  # append to the site's address to get the link to share
    expires_at: datetime


def user_out(view: UserView) -> UserOut:
    return UserOut(**view.__dict__)


def invite_out(issued: IssuedInvite) -> InviteOut:
    return InviteOut(
        user=user_out(issued.user),
        token=issued.token,
        invite_path=f"/accept-invite#token={issued.token}",
        expires_at=issued.expires_at,
    )


@router.get("/users")
def list_users(services: ServicesDep) -> list[UserOut]:
    return [user_out(view) for view in services.accounts.list_users()]


@router.post("/users", status_code=201)
def invite_user(body: InviteIn, services: ServicesDep) -> InviteOut:
    return invite_out(services.accounts.invite(body.email, body.role))


@router.post("/users/{user_id}/invite")
def reissue_invite(user_id: int, services: ServicesDep) -> InviteOut:
    return invite_out(services.accounts.reissue_invite(user_id))


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, services: ServicesDep) -> UserOut:
    return user_out(services.accounts.update_user(user_id, body.role, body.is_active))


@router.post("/users/{user_id}/reset-link")
def issue_reset_link(user_id: int, services: ServicesDep) -> InviteOut:
    return invite_out(services.accounts.issue_reset_link(user_id))


@router.delete("/users/{user_id}/invite")
def revoke_invite(user_id: int, services: ServicesDep) -> dict[str, str]:
    services.accounts.revoke_invite(user_id)
    return {"status": "ok"}
