from dataclasses import replace
from datetime import UTC, date, datetime

from app.ingestion.build import build_snapshot
from app.ingestion.window import DEFAULT_WINDOW

INGESTED_AT = datetime(2026, 10, 25, 10, 0, tzinfo=UTC)
ONE_DAY_WINDOW = replace(
    DEFAULT_WINDOW,
    fuelhh_settlement_from=date(2026, 1, 1),
    fuelhh_settlement_to=date(2026, 1, 1),
)


def windfor(publish: str, target: str, generation: int = 19000) -> dict[str, object]:
    return {
        "dataset": "WINDFOR",
        "publishTime": publish,
        "startTime": target,
        "generation": generation,
    }


def fuelhh(target: str, generation: int = 15000) -> dict[str, object]:
    return {
        "dataset": "FUELHH",
        "publishTime": target,
        "startTime": target,
        "fuelType": "WIND",
        "generation": generation,
    }


def test_keeps_one_row_per_publish_and_target_and_counts_the_duplicates():
    rows = [
        windfor("2026-01-01T07:30:00Z", "2026-01-01T08:00:00Z", 19000),
        windfor("2026-01-01T07:30:00Z", "2026-01-01T08:00:00Z", 19000),
        windfor("2026-01-01T07:30:00Z", "2026-01-01T09:00:00Z", 19100),
    ]

    snapshot = build_snapshot(rows, [], ONE_DAY_WINDOW, INGESTED_AT)

    assert [(f.target_time.hour, f.generation_mw) for f in snapshot.forecasts] == [
        (8, 19000),
        (9, 19100),
    ]
    assert snapshot.summary.forecast_duplicates_removed == 1


def test_excludes_forecasts_published_after_their_target_and_counts_them():
    rows = [
        windfor("2026-01-01T07:30:00Z", "2026-01-01T07:00:00Z"),  # published after target
        windfor("2026-01-01T07:30:00Z", "2026-01-01T08:00:00Z"),  # kept
        windfor("2026-01-01T08:00:00Z", "2026-01-01T08:00:00Z"),  # published exactly at target
    ]

    snapshot = build_snapshot(rows, [], ONE_DAY_WINDOW, INGESTED_AT)

    assert len(snapshot.forecasts) == 2
    assert all(f.publish_time <= f.target_time for f in snapshot.forecasts)
    assert snapshot.summary.excluded_forecasts == 1


def test_a_duplicate_of_an_excluded_row_is_counted_once_as_a_duplicate():
    late = windfor("2026-01-01T07:30:00Z", "2026-01-01T07:00:00Z")
    snapshot = build_snapshot([late, dict(late)], [], ONE_DAY_WINDOW, INGESTED_AT)

    assert snapshot.summary.forecast_duplicates_removed == 1
    assert snapshot.summary.excluded_forecasts == 1


def test_counts_malformed_rows_and_keeps_the_valid_ones():
    rows = [
        windfor("2026-01-01T07:30:00Z", "2026-01-01T08:00:00Z"),
        windfor("2026-01-01T07:30:00Z", "2026-01-01T09:00:00Z", generation=-5),
        {"dataset": "WINDFOR", "publishTime": "2026-01-01T07:30:00Z"},
    ]

    snapshot = build_snapshot(rows, [], ONE_DAY_WINDOW, INGESTED_AT)

    assert len(snapshot.forecasts) == 1
    assert snapshot.summary.forecast_rows_received == 3
    assert snapshot.summary.forecast_rows_malformed == 2


def test_counts_forecast_hours_with_no_forecast_between_the_first_and_last_target():
    rows = [
        windfor("2026-01-01T07:30:00Z", "2026-01-01T08:00:00Z"),
        windfor("2026-01-01T07:30:00Z", "2026-01-01T11:00:00Z"),
    ]

    snapshot = build_snapshot(rows, [], ONE_DAY_WINDOW, INGESTED_AT)

    # 09:00 and 10:00 have no forecast.
    assert snapshot.summary.forecast_gap_hours == 2


def test_counts_missing_half_hours_in_the_actuals_window():
    rows = [
        fuelhh(f"2026-01-01T{hour:02d}:{minute:02d}:00Z")
        for hour in range(0, 2)
        for minute in (0, 30)
    ]
    rows = rows[:-1]  # drop 01:30, so the window's 48 half-hours have 47 values

    snapshot = build_snapshot([], rows, ONE_DAY_WINDOW, INGESTED_AT)

    assert len(snapshot.actuals) == 3
    assert snapshot.summary.actual_gap_periods == 45


def test_removes_duplicate_actuals_by_target_time():
    rows = [
        fuelhh("2026-01-01T00:00:00Z", 15000),
        fuelhh("2026-01-01T00:00:00Z", 15000),
        fuelhh("2026-01-01T00:30:00Z", 15100),
    ]

    snapshot = build_snapshot([], rows, ONE_DAY_WINDOW, INGESTED_AT)

    assert [a.generation_mw for a in snapshot.actuals] == [15000, 15100]
    assert snapshot.summary.actual_duplicates_removed == 1


def test_output_is_sorted_and_carries_the_window_and_ingestion_time():
    rows = [
        windfor("2026-01-01T07:30:00Z", "2026-01-01T09:00:00Z"),
        windfor("2026-01-01T07:30:00Z", "2026-01-01T08:00:00Z"),
    ]
    actuals = [fuelhh("2026-01-01T00:30:00Z"), fuelhh("2026-01-01T00:00:00Z")]

    snapshot = build_snapshot(rows, actuals, ONE_DAY_WINDOW, INGESTED_AT)

    assert [f.target_time.hour for f in snapshot.forecasts] == [8, 9]
    assert [a.target_time.minute for a in snapshot.actuals] == [0, 30]
    assert snapshot.window == ONE_DAY_WINDOW
    assert snapshot.ingested_at == INGESTED_AT
