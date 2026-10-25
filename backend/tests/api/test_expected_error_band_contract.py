"""Expected-error band over the API: /decision-snapshot carries the band, /accuracy the coverage.

The snapshot is built so that every expected value can be worked out by hand:
- Each delivery day decides at 09:20 from a 07:30 run at 10000 MW, and at 09:30 from a 09:30 run at
  11000 MW, for every hour of the day.
- Actual generation is 10000 MW in every half-hour, except on 15 Jan, when it is 10500 MW.

So at 09:20 the error is 0 on every day except 15 Jan, where it is -500. At 09:30 the error is 1000
on every day except 15 Jan, where it is 500. A band over constant errors is flat, so the band for
an actual is simply the forecast shifted by the error.
"""

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pytest

from app.core.config import SNAPSHOT_PATH_ENV
from app.main import create_app
from app.repository.schema import SCHEMA_STATEMENTS

WARM_UP_FIRST = date(2025, 12, 19)
SCOPE_FIRST = date(2026, 1, 2)
SCOPE_LAST = date(2026, 2, 1)
SPIKE_DAY = date(2026, 1, 15)


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def _rows(first: date) -> tuple[list[tuple[datetime, datetime, int]], list[tuple[datetime, int]]]:
    """Forecasts (publish, target, MW) and half-hourly actuals (target, MW) from ``first`` to 1 Feb."""
    forecasts: list[tuple[datetime, datetime, int]] = []
    actuals: list[tuple[datetime, int]] = []
    for day in _days(first, SCOPE_LAST):
        early_run = datetime.combine(day - timedelta(days=1), time(7, 30))
        late_run = datetime.combine(day - timedelta(days=1), time(9, 30))
        start = datetime.combine(day, time(0))
        for hour in range(24):
            target = start + timedelta(hours=hour)
            forecasts.append((early_run, target, 10000))
            forecasts.append((late_run, target, 11000))
        actual = 10500 if day == SPIKE_DAY else 10000
        for half in range(48):
            actuals.append((start + timedelta(minutes=30 * half), actual))
    return forecasts, actuals


def _write_band_snapshot(path: Path, first: date) -> Path:
    forecasts, actuals = _rows(first)
    con = duckdb.connect(str(path))
    try:
        for statement in SCHEMA_STATEMENTS:
            con.execute(statement)
        con.executemany("INSERT INTO forecasts VALUES (?, ?, ?)", forecasts)
        con.executemany("INSERT INTO actuals VALUES (?, ?)", actuals)
        con.execute(
            "INSERT INTO ingestion_metadata VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0)",
            [
                datetime(2026, 10, 25, 10, 0),
                datetime(2025, 12, 18, 0, 0),
                datetime(2026, 2, 1, 23, 59),
                date(2025, 12, 19),
                date(2026, 2, 1),
                SCOPE_FIRST,
                SCOPE_LAST,
            ],
        )
    finally:
        con.close()
    return path


def _api(path: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.AsyncClient:
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(path))
    transport = httpx.ASGITransport(app=create_app())
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def band_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.AsyncClient:
    """Forecasts and actuals from the December warm-up, so every scope day has a full band."""
    return _api(_write_band_snapshot(tmp_path / "band.duckdb", WARM_UP_FIRST), monkeypatch)


@pytest.fixture
def no_warm_up_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.AsyncClient:
    """The same data starting on 2 Jan, so the first delivery days have no past errors."""
    return _api(_write_band_snapshot(tmp_path / "no-warm-up.duckdb", SCOPE_FIRST), monkeypatch)


async def _get(api: httpx.AsyncClient, path: str, **params: str) -> dict[str, Any]:
    response = await api.get(path, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_the_decision_snapshot_carries_the_band_for_its_delivery_day(
    band_api: httpx.AsyncClient,
):
    body = await _get(band_api, "/api/v1/decision-snapshot", delivery_day="2026-01-02")

    # The 14 past days all have zero error at 09:20, so the band is flat at zero.
    assert body["band"] == {"lower_error_mw": 0.0, "upper_error_mw": 0.0, "history_days": 14}
    first_hour = body["hours"][0]
    assert first_hour["forecast_mw"] == 10000.0
    assert first_hour["band_low_mw"] == 10000.0
    assert first_hour["band_high_mw"] == 10000.0


async def test_the_band_follows_the_selected_cutoff(band_api: httpx.AsyncClient):
    at_0920 = await _get(
        band_api, "/api/v1/decision-snapshot", delivery_day="2026-01-02", cutoff="09:20"
    )
    at_0930 = await _get(
        band_api, "/api/v1/decision-snapshot", delivery_day="2026-01-02", cutoff="09:30"
    )

    # At 09:30 the decision forecast is the 11000 MW run, and the past errors are 1000 MW.
    assert at_0930["band"]["lower_error_mw"] == 1000.0
    assert at_0930["band"]["upper_error_mw"] == 1000.0
    assert at_0930["hours"][0]["forecast_mw"] == 11000.0
    assert at_0930["hours"][0]["band_low_mw"] == 10000.0
    assert at_0930["band"] != at_0920["band"]


async def test_a_delivery_day_with_too_little_history_has_no_band(
    no_warm_up_api: httpx.AsyncClient,
):
    body = await _get(no_warm_up_api, "/api/v1/decision-snapshot", delivery_day="2026-01-02")

    assert body["band"] is None
    first_hour = body["hours"][0]
    assert first_hour["forecast_mw"] == 10000.0
    assert first_hour["band_low_mw"] is None
    assert first_hour["band_high_mw"] is None


async def test_accuracy_reports_band_coverage_over_every_scope_day(band_api: httpx.AsyncClient):
    body = await _get(band_api, "/api/v1/accuracy")

    coverage = body["band_coverage"]
    assert coverage["lookback_days"] == 14
    assert coverage["min_history_days"] == 7
    assert coverage["counted_hours"] == 31 * 24
    # 15 Jan is 500 MW out, so its 24 hours fall outside the band. Every other hour is inside.
    assert coverage["inside_hours"] == 31 * 24 - 24
    assert coverage["coverage_percent"] == pytest.approx((31 * 24 - 24) / (31 * 24) * 100)
    assert coverage["excluded_no_band"] == 0
    assert coverage["excluded_no_decision_forecast"] == 0
    assert coverage["excluded_no_actual"] == 0


async def test_without_the_warm_up_the_first_seven_days_have_no_band_and_are_not_counted(
    no_warm_up_api: httpx.AsyncClient,
):
    body = await _get(no_warm_up_api, "/api/v1/accuracy")

    # 2 to 8 Jan each have fewer than seven past days, so they have no band: 7 days, 168 hours.
    coverage = body["band_coverage"]
    assert coverage["excluded_no_band"] == 7 * 24
    assert coverage["counted_hours"] == (31 - 7) * 24
    assert coverage["inside_hours"] == (31 - 7) * 24 - 24
    counted = (31 - 7) * 24
    assert coverage["coverage_percent"] == pytest.approx((counted - 24) / counted * 100)
