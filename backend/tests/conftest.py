from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import duckdb
import httpx
import pytest
from fastapi import FastAPI

from app.main import create_app
from app.repository.schema import SCHEMA_STATEMENTS

# Hand-written expectations for the fixture snapshot below. They are not derived from the code.
FIXTURE_FORECASTS = (
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 1, 8, 0), 19000),
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 1, 9, 0), 19500),
    (datetime(2026, 1, 1, 23, 30), datetime(2026, 1, 2, 0, 0), 14000),
)
FIXTURE_ACTUALS = (
    (datetime(2026, 1, 2, 0, 0), 14100),
    (datetime(2026, 1, 2, 0, 30), 14200),
)


@pytest.fixture
def snapshot_file(tmp_path: Path) -> Path:
    """A small, hand-built snapshot with known coverage."""
    path = tmp_path / "fixture-snapshot.duckdb"
    con = duckdb.connect(str(path))
    try:
        for statement in SCHEMA_STATEMENTS:
            con.execute(statement)
        con.executemany("INSERT INTO forecasts VALUES (?, ?, ?)", FIXTURE_FORECASTS)
        con.executemany("INSERT INTO actuals VALUES (?, ?)", FIXTURE_ACTUALS)
        con.execute(
            "INSERT INTO ingestion_metadata VALUES "
            "(TIMESTAMP '2026-10-25 10:00:00', TIMESTAMP '2025-12-18 00:00:00', "
            "TIMESTAMP '2026-02-01 23:59:00', DATE '2025-12-19', DATE '2026-02-01', "
            "DATE '2026-01-02', DATE '2026-02-01', 4, 0, 1, 7, 0, 2, 0, 0, 2158)"
        )
    finally:
        con.close()
    return path


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "static"
    directory.mkdir()
    (directory / "index.html").write_text("<!doctype html><title>shell</title>", encoding="utf-8")
    return directory
