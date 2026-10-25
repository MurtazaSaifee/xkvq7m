"""Successful answers from the snapshot routes are cacheable. Health checks and errors are not."""

from pathlib import Path

import httpx
import pytest

from app.core.config import SNAPSHOT_PATH_ENV
from app.main import create_app

CACHE_CONTROL = "public, max-age=300, s-maxage=86400"
SNAPSHOT_ROUTES = [
    "/api/v1/meta",
    "/api/v1/decision-snapshot?delivery_day=2026-01-02",
    "/api/v1/accuracy?cutoff=09:20",
]


@pytest.fixture
def snapshot_client(decision_snapshot: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.AsyncClient:
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(decision_snapshot))
    transport = httpx.ASGITransport(app=create_app())
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def no_snapshot_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.AsyncClient:
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(tmp_path / "absent.duckdb"))
    transport = httpx.ASGITransport(app=create_app())
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.parametrize("path", SNAPSHOT_ROUTES)
async def test_a_successful_snapshot_answer_carries_the_cache_control(
    snapshot_client: httpx.AsyncClient, path: str
):
    async with snapshot_client as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert response.headers["cache-control"] == CACHE_CONTROL


async def test_health_is_not_cached(snapshot_client: httpx.AsyncClient):
    async with snapshot_client as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert "cache-control" not in response.headers


async def test_a_503_for_a_missing_snapshot_is_not_cached(no_snapshot_client: httpx.AsyncClient):
    async with no_snapshot_client as client:
        response = await client.get("/api/v1/meta")

    assert response.status_code == 503
    assert "cache-control" not in response.headers


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/decision-snapshot?delivery_day=2026-01-02&cutoff=25:00",
        "/api/v1/decision-snapshot?delivery_day=2030-01-01",
        "/api/v1/accuracy?cutoff=nope",
    ],
)
async def test_a_422_for_bad_parameters_is_not_cached(
    snapshot_client: httpx.AsyncClient, path: str
):
    async with snapshot_client as client:
        response = await client.get(path)

    assert response.status_code == 422
    assert "cache-control" not in response.headers
