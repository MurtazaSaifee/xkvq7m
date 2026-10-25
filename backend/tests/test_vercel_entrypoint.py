"""The Vercel Python function (``api/index.py``) serves the same app that uvicorn serves."""

import importlib.util
from types import ModuleType

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import REPO_ROOT, SNAPSHOT_PATH_ENV, snapshot_path
from app.main import STATIC_DIR_ENV

ENTRYPOINT = REPO_ROOT / "index.py"


def _load_entrypoint() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vercel_entrypoint", ENTRYPOINT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def entrypoint_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    # Production has neither override set: the snapshot comes from the bundled data dir.
    monkeypatch.delenv(SNAPSHOT_PATH_ENV, raising=False)
    monkeypatch.delenv(STATIC_DIR_ENV, raising=False)
    app = _load_entrypoint().app
    assert isinstance(app, FastAPI)
    return app


def test_the_entrypoint_exposes_a_fastapi_app_without_mounting_the_frontend(
    entrypoint_app: FastAPI,
):
    # Vercel serves the Vite build from its CDN, so the function must not mount static files.
    assert not any(getattr(route, "name", None) == "frontend" for route in entrypoint_app.routes)


async def test_the_entrypoint_serves_health(entrypoint_app: FastAPI):
    transport = httpx.ASGITransport(app=entrypoint_app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_the_entrypoint_reads_the_bundled_snapshot(entrypoint_app: FastAPI):
    assert snapshot_path() == REPO_ROOT / "data" / "snapshot.duckdb"
    assert snapshot_path().is_file()
    transport = httpx.ASGITransport(app=entrypoint_app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/meta")

    assert response.status_code == 200
    body = response.json()
    assert body["forecasts"]["row_count"] > 0
    assert body["actuals"]["row_count"] > 0
