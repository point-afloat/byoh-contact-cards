"""JSON API routes under /api."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from pydantic import BaseModel

from app.api_errors import ApiError
from app.contact import Contact
from app.deps import require_user
from app.extraction import ExtractionError, ExtractionResult
from app.fundraisingbox.client import CompanyMatch
from app.health import health_problems
from app.images import validate_and_prepare
from app.send import SendRequest, send_session
from app.services import Services, get_services
from app.sessions import Session
from app.validation import validate_contact

# Only the health check is public here; everything else needs a signed-in user.
public_router = APIRouter(prefix="/api")
router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
ServicesDep = Annotated[Services, Depends(get_services)]


class SessionOut(BaseModel):
    id: str
    contact: Contact | None
    warnings: list[str]
    sent: bool
    person_id: str | None = None
    record_type: str | None = None
    errors: dict[str, str] = {}


def session_out(session: Session) -> SessionOut:
    return SessionOut(
        id=session.id,
        contact=session.contact,
        warnings=[session.notice] if session.notice else [],
        sent=session.sent,
        person_id=session.person_id,
        record_type=session.record_type,
        errors=validate_contact(session.contact) if session.contact else {},
    )


@public_router.get("/health")
def health(request: Request, response: Response) -> dict[str, object]:
    """Unauthenticated liveness and readiness check for the platform.

    200 when the app is configured and the data directory is writable, otherwise 503 with the
    names of the problems. Never calls external services and never includes secrets.
    """
    problems = health_problems(request.app)
    if problems:
        response.status_code = 503
        return {"status": "unhealthy", "problems": problems}
    return {"status": "ok"}


@router.post("/sessions", status_code=201)
def create_session(services: ServicesDep, file: Annotated[UploadFile, File()]) -> SessionOut:
    """Upload a card image, extract its contents and open a review session."""
    max_bytes = services.settings.upload_max_bytes
    data = file.file.read(max_bytes + 1)  # never buffer more than the limit plus one byte
    image = validate_and_prepare(data, max_bytes)

    try:
        result = services.extraction.extract(image)
    except ExtractionError as exc:
        # The user can retry by uploading again or continue with an empty form.
        result = ExtractionResult(contact=Contact(), incomplete=True, notice=str(exc))

    session = services.store.create(image, result.contact, result.notice)
    return session_out(session)


@router.get("/sessions/{session_id}")
def get_session(session_id: str, services: ServicesDep) -> SessionOut:
    return session_out(services.store.get(session_id))


@router.get("/sessions/{session_id}/image")
def get_session_image(session_id: str, services: ServicesDep) -> Response:
    session = services.store.get(session_id)
    if session.image is None:
        raise ApiError(410, "image_discarded", "The card image was discarded after sending.")
    return Response(
        content=session.image.data,
        media_type=session.image.media_type,
        headers={"Cache-Control": "no-store"},
    )


@router.put("/sessions/{session_id}")
def update_session(session_id: str, contact: Contact, services: ServicesDep) -> SessionOut:
    return session_out(services.store.update_contact(session_id, contact))


@router.post("/sessions/{session_id}/send")
def send(session_id: str, body: SendRequest, services: ServicesDep) -> SessionOut:
    """Create the confirmed contact in FundraisingBox (company first when requested)."""
    return session_out(send_session(services, session_id, body))


@router.get("/companies")
def search_companies(
    services: ServicesDep, q: str = "", limit: Annotated[int, Query(ge=1, le=25)] = 10
) -> list[CompanyMatch]:
    """Search existing FundraisingBox companies. Failures surface as a clear 502/503."""
    return services.fundraisingbox.search_companies(q, limit)
