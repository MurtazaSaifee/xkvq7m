from datetime import date, datetime
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


def _write_snapshot(path: Path, delivery_first: date, delivery_last: date) -> Path:
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
            "?, ?, 8, 0, 0, 0, 0, 7, 0, 0, 0)",
            [delivery_first, delivery_last],
        )
    finally:
        con.close()
    return path


@pytest.fixture
def accuracy_snapshot(tmp_path: Path) -> Path:
    return _write_snapshot(
        tmp_path / "accuracy-snapshot.duckdb", date(2026, 1, 2), date(2026, 2, 1)
    )


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


async def test_the_scope_is_the_delivery_window_recorded_in_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # The December warm-up days are in scope when the snapshot's delivery window says so. The
    # January forecasts and actuals fall outside this window, so no hour can be measured.
    path = _write_snapshot(tmp_path / "warm-up.duckdb", date(2025, 12, 19), date(2026, 1, 1))
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(path))
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/accuracy")

    assert response.status_code == 200
    body = response.json()
    assert body["delivery_days"] == {"first": "2025-12-19", "last": "2026-01-01"}
    assert body["summary"]["target_hours"] == 14 * 24
    assert body["summary"]["measured_hours"] == 0


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


# Horizon curve. Every fixture forecast for 2 Jan is published at 07:30 on 1 Jan, except the 07:00
# row, published at 09:30. A target at 00:00 is therefore 16.5 h ahead, and each hour adds one.


async def _horizon(api: httpx.AsyncClient, cutoff: str = "09:20") -> dict[str, Any]:
    curve: dict[str, Any] = (await _accuracy(api, cutoff))["horizon_curve"]
    return curve


async def test_each_horizon_bucket_reports_its_mae_bias_and_sample_count(api: httpx.AsyncClient):
    buckets = {b["upper_hours"]: b for b in (await _horizon(api))["buckets"]}

    # Bucket 17 holds (16, 17] h, so the 00:00 target at 16.5 h. Errors: 900, -500, 0, 1000, -500,
    # 400 for the targets 00:00 to 05:00, at 16.5 h to 21.5 h.
    assert buckets[17] == {
        "lower_hours": 16,
        "upper_hours": 17,
        "mae_mw": 900,
        "bias_mw": 900,
        "sample_count": 1,
    }
    assert (buckets[18]["mae_mw"], buckets[18]["bias_mw"]) == (500, -500)
    assert (buckets[19]["mae_mw"], buckets[19]["bias_mw"]) == (0, 0)
    assert (buckets[20]["mae_mw"], buckets[20]["bias_mw"]) == (1000, 1000)
    assert (buckets[21]["mae_mw"], buckets[21]["bias_mw"]) == (500, -500)
    assert (buckets[22]["mae_mw"], buckets[22]["bias_mw"], buckets[22]["sample_count"]) == (
        400,
        400,
        1,
    )


async def test_buckets_run_from_one_hour_with_empty_ones_unmeasured(api: httpx.AsyncClient):
    buckets = (await _horizon(api))["buckets"]

    assert [b["upper_hours"] for b in buckets] == list(range(1, 24))
    assert buckets[0] == {
        "lower_hours": 0,
        "upper_hours": 1,
        "mae_mw": None,
        "bias_mw": None,
        "sample_count": 0,
    }
    # The 06:00 target is 22.5 h ahead with no actual, so bucket 23 is listed but unmeasured.
    assert (buckets[-1]["sample_count"], buckets[-1]["mae_mw"]) == (0, None)


async def test_forecasts_without_an_actual_are_counted_as_excluded_not_dropped(
    api: httpx.AsyncClient,
):
    curve = await _horizon(api)

    # The 06:00 and 07:00 forecasts have no actual, so six of the eight forecasts are measured.
    assert curve["excluded_no_actual"] == 2
    assert sum(b["sample_count"] for b in curve["buckets"]) == 6


async def test_the_decision_horizon_range_comes_from_the_decision_forecasts_at_the_cutoff(
    api: httpx.AsyncClient,
):
    # At 09:20 the decision forecasts are the 07:30 run for 00:00 to 06:00: 16.5 h to 22.5 h.
    assert (await _horizon(api, "09:20"))["decision_horizon_range_hours"] == {
        "min_hours": 16.5,
        "max_hours": 22.5,
    }
    # At 09:30 the 07:00 target is taken from the 09:30 run, 21.5 h ahead, inside the same range.
    assert (await _horizon(api, "09:30"))["decision_horizon_range_hours"] == {
        "min_hours": 16.5,
        "max_hours": 22.5,
    }


async def test_the_decision_horizon_range_is_null_when_no_decision_forecast_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = _write_snapshot(tmp_path / "early.duckdb", date(2026, 1, 2), date(2026, 2, 1))
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(path))
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 00:01 on the decision day is before the 07:30 run is published, so nothing is selected.
        response = await client.get("/api/v1/accuracy", params={"cutoff": "00:01"})

    assert response.status_code == 200
    assert response.json()["horizon_curve"]["decision_horizon_range_hours"] is None
