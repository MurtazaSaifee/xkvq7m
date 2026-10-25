"""Async httpx calls to the Elexon BMRS stream endpoints. Used by ingestion only, never the API."""

from datetime import datetime
from typing import cast

import httpx

from app.ingestion.window import IngestionWindow

ELEXON_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
REQUEST_TIMEOUT_SECONDS = 60.0


class IngestionError(RuntimeError):
    """Raised when Elexon answers with something other than a stream array."""


def create_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=ELEXON_BASE_URL,
        timeout=REQUEST_TIMEOUT_SECONDS,
        transport=transport,
    )


async def fetch_windfor(client: httpx.AsyncClient, window: IngestionWindow) -> list[object]:
    """All forecast rows whose publish time falls in the window. WINDFOR has no fuel filter."""
    return await _get_stream(
        client,
        "WINDFOR",
        {
            "publishDateTimeFrom": _iso_utc(window.windfor_publish_from),
            "publishDateTimeTo": _iso_utc(window.windfor_publish_to),
        },
    )


async def fetch_fuelhh_wind(client: httpx.AsyncClient, window: IngestionWindow) -> list[object]:
    """Wind actual generation for the settlement dates in the window."""
    return await _get_stream(
        client,
        "FUELHH",
        {
            "settlementDateFrom": window.fuelhh_settlement_from.isoformat(),
            "settlementDateTo": window.fuelhh_settlement_to.isoformat(),
            "fuelType": "WIND",
        },
    )


async def _get_stream(
    client: httpx.AsyncClient,
    dataset: str,
    params: dict[str, str],
) -> list[object]:
    response = await client.get(f"/datasets/{dataset}/stream", params=params)
    response.raise_for_status()
    body: object = response.json()
    if not isinstance(body, list):
        raise IngestionError(f"{dataset} stream returned {type(body).__name__}, expected a list")
    return cast(list[object], body)


def _iso_utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
