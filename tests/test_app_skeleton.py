from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api_errors import ApiError
from app.errors import ConfigError
from app.main import create_app


def client_with_routes() -> TestClient:
    app: FastAPI = create_app()

    class Body(BaseModel):
        name: str

    @app.post("/api/_echo")
    def echo(body: Body) -> dict[str, str]:
        return {"name": body.name}

    @app.get("/api/_api_error")
    def api_error() -> None:
        raise ApiError(409, "conflict", "Already there.")

    @app.get("/api/_config_error")
    def config_error() -> None:
        raise ConfigError("LLM_MODEL missing", code="config_error")

    @app.get("/api/_boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return TestClient(app, raise_server_exceptions=False)


def test_health_ok() -> None:
    res = TestClient(create_app()).get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_unknown_route_uses_uniform_error() -> None:
    res = client_with_routes().get("/api/nope")
    assert res.status_code == 404
    assert set(res.json()) == {"code", "message"}
    assert res.json()["code"] == "http_404"


def test_validation_error_uses_uniform_error() -> None:
    res = client_with_routes().post("/api/_echo", json={})
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"
    assert "name" in res.json()["message"]


def test_api_error_uses_its_status_and_code() -> None:
    res = client_with_routes().get("/api/_api_error")
    assert res.status_code == 409
    assert res.json() == {"code": "conflict", "message": "Already there."}


def test_config_error_is_503_with_message() -> None:
    res = client_with_routes().get("/api/_config_error")
    assert res.status_code == 503
    assert res.json() == {"code": "config_error", "message": "LLM_MODEL missing"}


def test_unexpected_error_does_not_leak_details() -> None:
    res = client_with_routes().get("/api/_boom")
    assert res.status_code == 500
    assert res.json()["code"] == "internal_error"
    assert "secret internal detail" not in res.text
