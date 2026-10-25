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


# A snapshot for decision selection. Each comment states the case a row exists to exercise.
# (publish_time, target_time, generation_mw)
DECISION_FORECASTS = (
    # Target 00:00: a run at 07:30, one published exactly at the 09:20 cutoff, and one after it.
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 0, 0), 10000),
    (datetime(2026, 1, 1, 9, 20), datetime(2026, 1, 2, 0, 0), 10100),
    (datetime(2026, 1, 1, 9, 50), datetime(2026, 1, 2, 0, 0), 10200),
    # Target 01:00: only a run published after the cutoff, so there is no decision forecast.
    (datetime(2026, 1, 1, 9, 30), datetime(2026, 1, 2, 1, 0), 9000),
    # Target 02:00: several runs cover it, and the latest one before the cutoff wins.
    (datetime(2025, 12, 31, 23, 0), datetime(2026, 1, 2, 2, 0), 500),
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 2, 0), 11000),
    # Target 03:00: a run published exactly at the cutoff, against an earlier one.
    (datetime(2025, 12, 31, 21, 0), datetime(2026, 1, 2, 3, 0), 12000),
    (datetime(2026, 1, 1, 9, 20), datetime(2026, 1, 2, 3, 0), 12100),
    # Target 04:00: published one minute after the cutoff, so it is not used.
    (datetime(2026, 1, 1, 9, 21), datetime(2026, 1, 2, 4, 0), 13000),
    # Target 05:00: only an early run.
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 5, 0), 13500),
    # Last delivery day in scope: 00:00 is selected, 23:00 is only covered after its cutoff.
    (datetime(2026, 1, 31, 7, 30), datetime(2026, 2, 1, 0, 0), 15000),
    (datetime(2026, 1, 31, 9, 30), datetime(2026, 2, 1, 23, 0), 16000),
)
# Cutoff edge cases for delivery day 5 Jan (decision day 4 Jan). A run published on 3 Jan at 22:30
# covers up to 21:00Z on 5 Jan, and the 02:30 run on 4 Jan is the first run of the decision day.
# A cutoff before 02:30 therefore falls back to the 22:30 run, which leaves 22:00 and 23:00 without
# a decision forecast.
CUTOFF_FORECASTS = (
    # The 22:30 run, for 20:00 and for its last target, 21:00.
    (datetime(2026, 1, 3, 22, 30), datetime(2026, 1, 5, 20, 0), 15300),
    (datetime(2026, 1, 3, 22, 30), datetime(2026, 1, 5, 21, 0), 15500),
    # The 02:30 run supersedes the 22:30 run at 21:00, and is the only run for 22:00 and 23:00.
    (datetime(2026, 1, 4, 2, 30), datetime(2026, 1, 5, 21, 0), 15600),
    (datetime(2026, 1, 4, 2, 30), datetime(2026, 1, 5, 22, 0), 16200),
    (datetime(2026, 1, 4, 2, 30), datetime(2026, 1, 5, 23, 0), 16300),
)
DECISION_ACTUALS = (
    (datetime(2026, 1, 1, 23, 30), 1),  # the decision day, not delivery: must not be returned
    (datetime(2026, 1, 2, 0, 0), 14000),
    (datetime(2026, 1, 2, 0, 30), 14200),
    (datetime(2026, 2, 1, 23, 30), 9000),
)


@pytest.fixture
def decision_snapshot(tmp_path: Path) -> Path:
    """A small snapshot covering the decision-forecast edge cases; delivery days 2 Jan to 1 Feb."""
    path = tmp_path / "decision-snapshot.duckdb"
    con = duckdb.connect(str(path))
    try:
        for statement in SCHEMA_STATEMENTS:
            con.execute(statement)
        con.executemany("INSERT INTO forecasts VALUES (?, ?, ?)", DECISION_FORECASTS)
        con.executemany("INSERT INTO forecasts VALUES (?, ?, ?)", CUTOFF_FORECASTS)
        con.executemany("INSERT INTO actuals VALUES (?, ?)", DECISION_ACTUALS)
        con.execute(
            "INSERT INTO ingestion_metadata VALUES "
            "(TIMESTAMP '2026-10-25 10:00:00', TIMESTAMP '2025-12-18 00:00:00', "
            "TIMESTAMP '2026-02-01 23:59:00', DATE '2025-12-19', DATE '2026-02-01', "
            "DATE '2026-01-02', DATE '2026-02-01', 12, 0, 0, 0, 0, 4, 0, 0, 0)"
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
