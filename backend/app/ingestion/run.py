"""One ingestion run: fetch both datasets concurrently, build the snapshot, log it, and write it."""

import asyncio
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.ingestion.build import SnapshotData, build_snapshot
from app.ingestion.elexon import create_client, fetch_fuelhh_wind, fetch_windfor
from app.ingestion.store import write_snapshot
from app.ingestion.window import DEFAULT_WINDOW, IngestionWindow

logger = logging.getLogger(__name__)


async def _fetch_both(
    window: IngestionWindow,
    transport: httpx.AsyncBaseTransport | None,
) -> tuple[list[object], list[object]]:
    async with create_client(transport) as client:
        windfor_rows, fuelhh_rows = await asyncio.gather(
            fetch_windfor(client, window),
            fetch_fuelhh_wind(client, window),
        )
    return windfor_rows, fuelhh_rows


def run_ingestion(
    output: Path,
    window: IngestionWindow = DEFAULT_WINDOW,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SnapshotData:
    """Fetch, clean and write the snapshot to ``output``. Nothing is written if a fetch fails."""
    windfor_rows, fuelhh_rows = asyncio.run(_fetch_both(window, transport))
    snapshot = build_snapshot(windfor_rows, fuelhh_rows, window, datetime.now(UTC))
    logger.info("ingestion validation summary", extra={"validation": asdict(snapshot.summary)})
    write_snapshot(snapshot, output)
    logger.info("snapshot written", extra={"path": str(output)})
    return snapshot
