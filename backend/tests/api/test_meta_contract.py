from pathlib import Path

import httpx
import pytest

from app.core.config import SNAPSHOT_PATH_ENV
from app.main import create_app


async def test_meta_reports_the_snapshot_coverage(
    snapshot_file: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(snapshot_file))
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "ingested_at": "2026-10-25T10:00:00Z",
        "forecasts": {
            "first_target_time": "2026-01-01T08:00:00Z",
            "last_target_time": "2026-01-02T00:00:00Z",
            "row_count": 3,
        },
        "actuals": {
            "first_target_time": "2026-01-02T00:00:00Z",
            "last_target_time": "2026-01-02T00:30:00Z",
            "row_count": 2,
        },
        "excluded_forecasts": 7,
        "delivery_days": {"first": "2026-01-02", "last": "2026-02-01"},
    }


async def test_meta_is_503_when_there_is_no_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(tmp_path / "absent.duckdb"))
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/meta")

    assert response.status_code == 503


async def test_meta_without_a_snapshot_answers_the_shared_503_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(tmp_path / "absent.duckdb"))
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/meta")

    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "type": "about:blank",
        "title": "Service Unavailable",
        "status": 503,
        "detail": "Data snapshot is not available",
        "instance": "/api/v1/meta",
    }


async def test_openapi_documents_the_meta_route():
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        document = (await client.get("/openapi.json")).json()

    assert "/api/v1/meta" in document["paths"]
