"""Every answer carries the four security headers: API, unknown routes, the frontend and errors."""

from pathlib import Path

import httpx
import pytest

from app.core.config import SNAPSHOT_PATH_ENV
from app.main import create_app

EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "x-frame-options": "DENY",
    "content-security-policy": "frame-ancestors 'none'",
}


def assert_security_headers(response: httpx.Response) -> None:
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers.get(name) == value, name


@pytest.fixture
def corrupt_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A snapshot file that exists but is not DuckDB, so reading it raises an unexpected error."""
    path = tmp_path / "corrupt.duckdb"
    path.write_bytes(b"this is not a duckdb file" * 100)
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(path))
    return path


async def test_an_api_answer_carries_the_security_headers(client: httpx.AsyncClient):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert_security_headers(response)


async def test_an_unknown_route_carries_the_security_headers(client: httpx.AsyncClient):
    response = await client.get("/no-such-page")

    assert response.status_code == 404
    assert_security_headers(response)


async def test_the_frontend_shell_carries_the_security_headers(
    static_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("WIND_STATIC_DIR", str(static_dir))
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert_security_headers(response)


async def test_an_unexpected_error_carries_the_security_headers(corrupt_snapshot: Path):
    # The unexpected-error answer is sent outside the middleware stack, so it sets its own headers.
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/meta")

    assert response.status_code == 500
    assert_security_headers(response)
