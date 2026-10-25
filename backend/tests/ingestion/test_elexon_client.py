from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.ingestion.elexon import IngestionError, fetch_fuelhh_wind, fetch_windfor
from app.ingestion.window import DEFAULT_WINDOW

Handler = Callable[[httpx.Request], httpx.Response]


def client_for(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://data.elexon.co.uk/bmrs/api/v1",
        transport=httpx.MockTransport(handler),
    )


def json_response(body: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=body)


async def test_windfor_request_filters_on_publish_time_in_utc():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response([{"publishTime": "2026-01-01T07:30:00Z"}])

    async with client_for(handler) as client:
        rows = await fetch_windfor(client, DEFAULT_WINDOW)

    assert rows == [{"publishTime": "2026-01-01T07:30:00Z"}]
    request = seen[0]
    assert request.url.path == "/bmrs/api/v1/datasets/WINDFOR/stream"
    assert request.url.params["publishDateTimeFrom"] == "2025-12-18T00:00:00Z"
    assert request.url.params["publishDateTimeTo"] == "2026-02-01T23:59:00Z"
    assert "fuelType" not in request.url.params


async def test_fuelhh_request_filters_on_settlement_date_and_wind_only():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response([])

    async with client_for(handler) as client:
        await fetch_fuelhh_wind(client, DEFAULT_WINDOW)

    request = seen[0]
    assert request.url.path == "/bmrs/api/v1/datasets/FUELHH/stream"
    assert request.url.params["settlementDateFrom"] == "2025-12-19"
    assert request.url.params["settlementDateTo"] == "2026-02-01"
    assert request.url.params["fuelType"] == "WIND"


async def test_a_body_that_is_not_a_list_is_an_ingestion_error():
    async with client_for(lambda _: json_response({"data": []})) as client:
        with pytest.raises(IngestionError):
            await fetch_windfor(client, DEFAULT_WINDOW)


async def test_an_http_error_is_raised_rather_than_ingesting_partial_data():
    async with client_for(lambda _: httpx.Response(503)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_fuelhh_wind(client, DEFAULT_WINDOW)
