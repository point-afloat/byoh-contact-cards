# src/api/main.py

from fastapi import FastAPI
from api.routes.extract import router as extract_router

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app: FastAPI = FastAPI(title="Contact Card API")
app.include_router(extract_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "message": "Contact card API is running"}
