import logging
import re

import httpx
import pytest

HEX_32 = re.compile(r"^[0-9a-f]{32}$")


async def test_echoes_incoming_request_id(client: httpx.AsyncClient):
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc-123"})

    assert response.headers["x-request-id"] == "trace-abc-123"


async def test_generates_request_id_when_header_absent(client: httpx.AsyncClient):
    response = await client.get("/api/v1/health")

    assert HEX_32.match(response.headers["x-request-id"])


@pytest.mark.parametrize("bad_id", ["has spaces inside", "x" * 129, "semi;colon"])
async def test_replaces_unsafe_incoming_request_id(client: httpx.AsyncClient, bad_id: str):
    response = await client.get("/api/v1/health", headers={"X-Request-ID": bad_id})

    assert response.headers["x-request-id"] != bad_id
    assert HEX_32.match(response.headers["x-request-id"])


async def test_access_log_record_carries_request_id(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.INFO, logger="app.access")

    await client.get("/api/v1/health", headers={"X-Request-ID": "log-me-42"})

    access = [r for r in caplog.records if r.name == "app.access"]
    assert len(access) == 1
    fields = vars(access[0])
    assert fields["request_id"] == "log-me-42"
    assert fields["method"] == "GET"
    assert fields["path"] == "/api/v1/health"
    assert fields["status"] == 200
    assert fields["duration_ms"] >= 0
