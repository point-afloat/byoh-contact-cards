# tests/test_api.py

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_extract_rejects_unknown_engine():
    response = client.post(
        "/extract",
        params={"engine": "not_real"},
        files={"file": ("test.png", b"fake image bytes", "image/png")},
    )
    assert response.status_code == 400
    assert "Unknown engine" in response.json()["detail"]
