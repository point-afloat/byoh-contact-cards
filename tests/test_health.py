import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app
from app.services import build_services

LLM_KEY = "llm-secret-key-123"
FB_TOKEN = "fb-secret-token-456"


def client_for(data_dir: Path, **overrides: object) -> TestClient:
    settings = load_settings(
        _env_file=None,
        llm_model="tiny",
        llm_api_key=LLM_KEY,
        fundraisingbox_apitoken=FB_TOKEN,
        initial_admin_email="admin@example.org",
        initial_admin_password="a very long admin password",
        data_dir=data_dir,
        **overrides,
    )
    return TestClient(create_app(build_services(settings)))


@pytest.fixture
def healthy(tmp_path: Path) -> Iterator[TestClient]:
    with client_for(tmp_path) as client:
        yield client


def test_healthy_when_configured_and_data_dir_writable(healthy: TestClient) -> None:
    res = healthy.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_healthy_body_contains_no_secrets(healthy: TestClient) -> None:
    text = healthy.get("/api/health").text
    assert LLM_KEY not in text and FB_TOKEN not in text


def test_health_needs_no_authentication_or_session(healthy: TestClient) -> None:
    assert healthy.get("/api/health", headers={}).status_code == 200


def test_missing_llm_model_is_unhealthy_and_named() -> None:
    with TestClient(create_app()) as bare:  # nothing configured at all
        res = bare.get("/api/health")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "unhealthy"
    assert any("LLM_MODEL" in problem for problem in body["problems"])


def test_missing_llm_api_key_for_a_hosted_endpoint_is_unhealthy_without_leaking_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LLM_MODEL", "tiny")
    monkeypatch.setenv("FUNDRAISINGBOX_APITOKEN", FB_TOKEN)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)  # no .env file is picked up
    with TestClient(create_app()) as client:
        res = client.get("/api/health")
    assert res.status_code == 503
    assert any("LLM_API_KEY" in p for p in res.json()["problems"])
    assert FB_TOKEN not in res.text


def test_missing_fundraisingbox_token_is_unhealthy_and_named(tmp_path: Path) -> None:
    settings = load_settings(
        _env_file=None,
        llm_model="m",
        llm_api_key=LLM_KEY,
        data_dir=tmp_path,
        initial_admin_email="admin@example.org",
        initial_admin_password="a very long admin password",
    )
    with TestClient(create_app(build_services(settings))) as client:
        res = client.get("/api/health")
    assert res.status_code == 503
    assert res.json()["problems"] == ["FUNDRAISINGBOX_APITOKEN is not set"]
    assert LLM_KEY not in res.text


def test_missing_data_dir_is_unhealthy(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with client_for(missing) as client:
        res = client.get("/api/health")
    assert res.status_code == 503
    assert any("DATA_DIR" in p and "does not exist" in p for p in res.json()["problems"])


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write to read-only directories")
def test_unwritable_data_dir_is_unhealthy(tmp_path: Path) -> None:
    read_only = tmp_path / "ro"
    read_only.mkdir()
    read_only.chmod(0o500)
    try:
        with client_for(read_only) as client:
            res = client.get("/api/health")
    finally:
        read_only.chmod(0o700)
    assert res.status_code == 503
    assert any("not writable" in p for p in res.json()["problems"])


def test_health_check_leaves_no_files_behind(healthy: TestClient, tmp_path: Path) -> None:
    before = sorted(p.name for p in tmp_path.iterdir())
    healthy.get("/api/health")
    assert sorted(p.name for p in tmp_path.iterdir()) == before == ["app.db"]  # no probe files


def test_startup_logs_each_problem_without_secrets(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = load_settings(
        _env_file=None, llm_model="m", llm_api_key=LLM_KEY, data_dir=tmp_path / "nope"
    )
    with caplog.at_level(logging.INFO):
        with TestClient(create_app(build_services(settings))):
            pass
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("FUNDRAISINGBOX_APITOKEN" in e for e in errors)
    assert any("DATA_DIR" in e for e in errors)
    assert LLM_KEY not in caplog.text


def test_startup_logs_ok_when_everything_is_configured(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        with client_for(tmp_path):
            pass
    assert "Configuration OK" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_startup_logs_a_clear_line_for_missing_configuration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        with TestClient(create_app()):
            pass
    assert "LLM_MODEL" in caplog.text


def test_startup_migrates_the_database_so_the_app_is_healthy(tmp_path: Path) -> None:
    assert not (tmp_path / "app.db").exists()
    with client_for(tmp_path) as client:
        assert (tmp_path / "app.db").is_file()
        assert client.get("/api/health").status_code == 200


def test_without_startup_the_uninitialised_database_is_reported(tmp_path: Path) -> None:
    client = client_for(tmp_path)  # no `with`: the startup step never runs
    res = client.get("/api/health")
    assert res.status_code == 503
    assert any("not been initialised" in p for p in res.json()["problems"])
    assert not (tmp_path / "app.db").exists()  # the check did not create the file
