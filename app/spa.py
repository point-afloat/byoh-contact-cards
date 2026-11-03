"""Serving the built React app (frontend/dist) from the same process as the API.

Unknown paths fall back to index.html so deep links and reloads work, except under /api,
which keeps its uniform JSON errors. When no build exists (development), only the API runs.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def default_static_dir() -> Path:
    override = os.environ.get("STATIC_DIR", "").strip()
    return Path(override) if override else DEFAULT_STATIC_DIR


def mount_spa(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        return
    root = dist.resolve()

    assets = root / "assets"
    if assets.is_dir():  # hashed filenames: safe to cache for a long time
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not Found")  # keep the JSON error body for API paths
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
