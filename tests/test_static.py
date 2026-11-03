from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

INDEX = "<!doctype html><title>Contact card importer</title><div id=root></div>"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    site = tmp_path / "site" / "dist"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text(INDEX)
    (site / "assets" / "app-abc123.js").write_text("console.log('app')")
    (site / "favicon.svg").write_text("<svg/>")
    (tmp_path / "site" / "secret.txt").write_text("TOP SECRET")  # outside dist
    return site


@pytest.fixture
def client(dist: Path) -> TestClient:
    return TestClient(create_app(static_dir=dist))


def test_root_serves_the_app_and_is_not_cached(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code == 200 and "Contact card importer" in res.text
    assert res.headers["cache-control"] == "no-cache"


def test_deep_links_and_reloads_fall_back_to_index(client: TestClient) -> None:
    res = client.get("/anything/at/all")
    assert res.status_code == 200 and res.text == INDEX


def test_built_assets_are_served(client: TestClient) -> None:
    res = client.get("/assets/app-abc123.js")
    assert res.status_code == 200 and "console.log" in res.text


def test_files_in_the_dist_root_are_served(client: TestClient) -> None:
    assert client.get("/favicon.svg").text == "<svg/>"


def test_unknown_api_paths_keep_the_json_error_not_the_app(client: TestClient) -> None:
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.json()["code"] == "http_404"
    assert "html" not in res.headers["content-type"]


def test_api_routes_still_win_over_the_fallback(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.headers["content-type"].startswith("application/json")
    assert res.json()["status"] in {"ok", "unhealthy"}


@pytest.mark.parametrize(
    "path", ["/%2e%2e/secret.txt", "/..%2fsecret.txt", "/assets/..%2f..%2fsecret.txt"]
)
def test_paths_outside_the_build_are_never_served(client: TestClient, path: str) -> None:
    res = client.get(path)
    assert "TOP SECRET" not in res.text


def test_without_a_build_only_the_api_runs(tmp_path: Path) -> None:
    api_only = TestClient(create_app(static_dir=tmp_path / "missing"))
    res = api_only.get("/")
    assert res.status_code == 404 and res.json()["code"] == "http_404"
    assert api_only.get("/api/health").status_code in {200, 503}


def test_static_dir_can_come_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, dist: Path
) -> None:
    monkeypatch.setenv("STATIC_DIR", str(dist))
    assert "Contact card importer" in TestClient(create_app()).get("/").text
