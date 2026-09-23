# src/api/routes/extract.py

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pdf2image import convert_from_path
from PIL import Image
from pydantic import BaseModel

from ingestion.ingestion import Contact, extract_fields

router = APIRouter()

ALLOWED_ENGINES = {"local_vlm"}


class ExtractResponse(BaseModel):
    engine: str
    contact: Contact
    warning: str | None = None


@router.post("/extract", response_model=ExtractResponse)
async def extract(
    file: UploadFile = File(...), engine: str = "local_vlm"  # noqa: B008
) -> ExtractResponse:
    """Extract contact fields from an uploaded card (PDF or image)."""
    if engine not in ALLOWED_ENGINES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown engine '{engine}'. Choose from {sorted(ALLOWED_ENGINES)}.",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        if suffix.lower() == ".pdf":
            pages = convert_from_path(tmp_path)
            image = pages[0]
            page_count = len(pages)
        else:
            image = Image.open(tmp_path)
            page_count = 1

        try:
            contact = extract_fields(image, engine=engine)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

        warning_msg = (
            f"PDF had {page_count} pages — only the first was processed."
            if page_count > 1
            else None
        )

        return ExtractResponse(engine=engine, contact=contact, warning=warning_msg)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
