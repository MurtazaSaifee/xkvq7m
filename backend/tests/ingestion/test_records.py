from datetime import datetime

import pytest

from app.ingestion.records import (
    Actual,
    Forecast,
    MalformedRecordError,
    parse_actual,
    parse_forecast,
)


def windfor_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "dataset": "WINDFOR",
        "publishTime": "2026-01-01T07:30:00Z",
        "startTime": "2026-01-01T08:00:00Z",
        "generation": 19378,
    }
    row.update(overrides)
    return row


def fuelhh_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "dataset": "FUELHH",
        "publishTime": "2026-01-02T00:00:00Z",
        "startTime": "2026-01-01T23:30:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 48,
        "fuelType": "WIND",
        "generation": 15538,
    }
    row.update(overrides)
    return row


def test_parses_a_windfor_row_into_a_forecast_with_naive_utc_times():
    assert parse_forecast(windfor_row()) == Forecast(
        publish_time=datetime(2026, 1, 1, 7, 30),
        target_time=datetime(2026, 1, 1, 8, 0),
        generation_mw=19378,
    )


def test_converts_offset_timestamps_to_utc():
    forecast = parse_forecast(windfor_row(publishTime="2026-01-01T08:30:00+01:00"))

    assert forecast.publish_time == datetime(2026, 1, 1, 7, 30)


def test_parses_a_fuelhh_row_into_an_actual_keyed_on_its_start_time():
    assert parse_actual(fuelhh_row()) == Actual(
        target_time=datetime(2026, 1, 1, 23, 30),
        generation_mw=15538,
    )


def test_accepts_zero_generation():
    assert parse_forecast(windfor_row(generation=0)).generation_mw == 0


@pytest.mark.parametrize(
    "override",
    [
        {"startTime": "2026-01-01T08:00:00"},  # no timezone
        {"startTime": "yesterday"},
        {"publishTime": None},
        {"generation": "19378"},
        {"generation": 19378.5},
        {"generation": True},
        {"generation": -1},
        {"generation": 1_000_000},
        {"startTime": "2026-01-01T08:30:00Z"},  # WINDFOR is hourly
    ],
)
def test_rejects_malformed_windfor_rows(override: dict[str, object]):
    with pytest.raises(MalformedRecordError):
        parse_forecast(windfor_row(**override))


def test_rejects_a_windfor_row_missing_a_field():
    row = windfor_row()
    del row["generation"]

    with pytest.raises(MalformedRecordError):
        parse_forecast(row)


@pytest.mark.parametrize(
    "override",
    [
        {"startTime": "2026-01-01T23:45:00Z"},  # FUELHH is half-hourly
        {"generation": None},
    ],
)
def test_rejects_malformed_fuelhh_rows(override: dict[str, object]):
    with pytest.raises(MalformedRecordError):
        parse_actual(fuelhh_row(**override))


def test_rejects_a_row_that_is_not_an_object():
    with pytest.raises(MalformedRecordError):
        parse_forecast("19378")
