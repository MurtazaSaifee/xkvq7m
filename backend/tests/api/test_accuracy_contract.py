from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pytest

from app.core.config import SNAPSHOT_PATH_ENV
from app.main import create_app
from app.repository.schema import SCHEMA_STATEMENTS

PROBLEM_MEDIA_TYPE = "application/problem+json"

# Forecasts for 2 Jan 2026 published at 07:30 on 1 Jan, so they are in time for a 09:20 cutoff.
# A forecast for 07:00 is published at 09:30, so it is only in time for a cutoff of 09:30 or later.
# (publish_time, target_time, generation_mw)
ACCURACY_FORECASTS = (
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 0, 0), 19000),
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 1, 0), 18000),
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 2, 0), 17000),
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 3, 0), 15000),
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 4, 0), 12000),
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 5, 0), 12500),
    # No actual for 06:00, so the hour is excluded as no actual.
    (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 2, 6, 0), 12000),
    (datetime(2026, 1, 1, 9, 30), datetime(2026, 1, 2, 7, 0), 9000),
)
# (target_time, generation_mw), half-hourly. Each hour's actual is the mean of its two halves.
ACCURACY_ACTUALS = (
    (datetime(2026, 1, 2, 0, 0), 18000),
    (datetime(2026, 1, 2, 0, 30), 18200),
    (datetime(2026, 1, 2, 1, 0), 18500),
    (datetime(2026, 1, 2, 1, 30), 18500),
    (datetime(2026, 1, 2, 2, 0), 16900),
    (datetime(2026, 1, 2, 2, 30), 17100),
    (datetime(2026, 1, 2, 3, 0), 14000),
    (datetime(2026, 1, 2, 3, 30), 14000),
    (datetime(2026, 1, 2, 4, 0), 12500),
    (datetime(2026, 1, 2, 4, 30), 12500),
    (datetime(2026, 1, 2, 5, 0), 12000),
    (datetime(2026, 1, 2, 5, 30), 12200),
)


@pytest.fixture
def accuracy_snapshot(tmp_path: Path) -> Path:
    path = tmp_path / "accuracy-snapshot.duckdb"
    con = duckdb.connect(str(path))
    try:
        for statement in SCHEMA_STATEMENTS:
            con.execute(statement)
        con.executemany(
            "INSERT INTO forecasts VALUES (?, ?, ?)",
            [(publish, target, mw) for publish, target, mw in ACCURACY_FORECASTS],
        )
        con.executemany("INSERT INTO actuals VALUES (?, ?)", ACCURACY_ACTUALS)
        con.execute(
            "INSERT INTO ingestion_metadata VALUES "
            "(TIMESTAMP '2026-10-25 10:00:00', TIMESTAMP '2025-12-18 00:00:00', "
            "TIMESTAMP '2026-02-01 23:59:00', DATE '2025-12-19', DATE '2026-02-01', "
            "DATE '2026-01-02', DATE '2026-02-01', 8, 0, 0, 0, 0, 7, 0, 0, 0)"
        )
    finally:
        con.close()
    return path


@pytest.fixture
def api(accuracy_snapshot: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.AsyncClient:
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(accuracy_snapshot))
    transport = httpx.ASGITransport(app=create_app())
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _accuracy(api: httpx.AsyncClient, cutoff: str | None = None) -> dict[str, Any]:
    params = {} if cutoff is None else {"cutoff": cutoff}
    response = await api.get("/api/v1/accuracy", params=params)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


async def test_the_summary_is_computed_over_the_measured_hours_only(api: httpx.AsyncClient):
    body = await _accuracy(api)

    summary = body["summary"]
    # Hour errors: 900, -500, 0, 1000, -500, 400. Mean actual is 92200 / 6.
    assert summary["target_hours"] == 31 * 24
    assert summary["measured_hours"] == 6
    assert summary["excluded_no_decision_forecast"] == 31 * 24 - 7
    assert summary["excluded_no_actual"] == 1
    assert summary["mae_mw"] == pytest.approx(550)
    assert summary["bias_mw"] == pytest.approx(1300 / 6)
    assert summary["rmse_mw"] == pytest.approx((2470000 / 6) ** 0.5)
    assert summary["p90_abs_error_mw"] == pytest.approx(950)
    assert summary["mean_actual_mw"] == pytest.approx(92200 / 6)
    assert summary["nmae_percent"] == pytest.approx(3300 / 92200 * 100)


async def test_the_histogram_has_fixed_500_mw_bins_that_count_every_measured_hour(
    api: httpx.AsyncClient,
):
    body = await _accuracy(api)

    histogram = body["histogram"]
    assert histogram["bin_width_mw"] == 500
    assert histogram["bins"] == [
        {"lower_mw": -500, "upper_mw": 0, "count": 2},
        {"lower_mw": 0, "upper_mw": 500, "count": 2},
        {"lower_mw": 500, "upper_mw": 1000, "count": 2},
    ]


async def test_the_response_states_the_cutoff_and_the_delivery_days_in_scope(
    api: httpx.AsyncClient,
):
    body = await _accuracy(api)

    assert body["cutoff"] == "09:20"
    assert body["delivery_days"] == {"first": "2026-01-02", "last": "2026-02-01"}


async def test_the_shared_cutoff_changes_which_forecasts_are_measured(api: httpx.AsyncClient):
    at_0920 = await _accuracy(api, "09:20")
    at_0930 = await _accuracy(api, "09:30")

    # At 09:30 the 07:00 forecast is in time, but it has no actual, so it is counted as no actual.
    assert at_0930["cutoff"] == "09:30"
    assert at_0930["summary"]["measured_hours"] == 6
    assert at_0930["summary"]["excluded_no_actual"] == 2
    assert at_0930["summary"]["excluded_no_decision_forecast"] == 31 * 24 - 8
    assert at_0920["summary"]["excluded_no_actual"] == 1


async def test_an_invalid_cutoff_is_a_422_problem(api: httpx.AsyncClient):
    async with api:
        response = await api.get("/api/v1/accuracy", params={"cutoff": "9:20"})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert response.json()["errors"][0]["loc"] == ["query", "cutoff"]


async def test_a_missing_snapshot_is_a_503_problem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(tmp_path / "absent.duckdb"))
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/accuracy")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)


async def test_openapi_documents_the_accuracy_route_and_its_cutoff_parameter():
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        document = (await client.get("/openapi.json")).json()

    operation = document["paths"]["/api/v1/accuracy"]["get"]
    assert {p["name"] for p in operation["parameters"]} == {"cutoff"}
    assert PROBLEM_MEDIA_TYPE in operation["responses"]["503"]["content"]
