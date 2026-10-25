"""Unexpected errors are answered as RFC 7807 problems too, with no stack trace in the body."""

import logging
import re
from pathlib import Path

import httpx
import pytest

from app.core.config import SNAPSHOT_PATH_ENV
from app.main import create_app

PROBLEM_MEDIA_TYPE = "application/problem+json"
HEX_32 = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture
def corrupt_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A snapshot file that exists but is not DuckDB, so reading it raises an unexpected error."""
    path = tmp_path / "corrupt.duckdb"
    path.write_bytes(b"this is not a duckdb file" * 100)
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(path))
    return path


@pytest.fixture
async def unexpected_error_client(corrupt_snapshot: Path):
    # Let the server error reach the client as a response, not as an exception in the test.
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_an_unexpected_error_is_a_500_problem_with_a_generic_detail(
    unexpected_error_client: httpx.AsyncClient,
):
    response = await unexpected_error_client.get("/api/v1/meta")

    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    problem = response.json()
    assert problem["type"] == "about:blank"
    assert problem["title"] == "Internal Server Error"
    assert problem["status"] == 500
    assert problem["detail"] == "An unexpected error occurred. The server has logged it."
    assert problem["instance"] == "/api/v1/meta"


async def test_an_unexpected_error_body_holds_no_stack_trace(
    unexpected_error_client: httpx.AsyncClient,
):
    response = await unexpected_error_client.get("/api/v1/meta")

    assert "Traceback" not in response.text
    assert "duckdb" not in response.text.lower()
    assert "exc_info" not in response.json()


async def test_an_unexpected_error_echoes_the_request_id_the_log_line_carries(
    unexpected_error_client: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.ERROR, logger="app.errors")

    response = await unexpected_error_client.get(
        "/api/v1/meta", headers={"X-Request-ID": "boom-42"}
    )

    assert response.headers["x-request-id"] == "boom-42"
    errors = [r for r in caplog.records if r.name == "app.errors"]
    assert len(errors) == 1
    record = errors[0]
    assert vars(record)["request_id"] == "boom-42"
    assert record.exc_info is not None
    assert record.exc_info[1] is not None


async def test_an_unexpected_error_without_an_incoming_id_still_gets_a_request_id(
    unexpected_error_client: httpx.AsyncClient,
):
    response = await unexpected_error_client.get("/api/v1/meta")

    assert HEX_32.match(response.headers["x-request-id"])


async def test_handled_errors_still_return_their_own_problem_status(client: httpx.AsyncClient):
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
