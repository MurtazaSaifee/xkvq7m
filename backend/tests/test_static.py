from pathlib import Path

import httpx
import pytest

from app.main import create_app


async def test_serves_frontend_shell_when_static_dir_is_configured(
    static_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WIND_STATIC_DIR", str(static_dir))
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        root = await client.get("/")
        health = await client.get("/api/v1/health")

    assert root.status_code == 200
    assert "<title>shell</title>" in root.text
    assert health.json() == {"status": "ok"}


async def test_root_is_not_found_without_static_dir(client: httpx.AsyncClient):
    response = await client.get("/")

    assert response.status_code == 404
