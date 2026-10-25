"""Turn raw Elexon rows into the clean records the snapshot stores.

Pure functions only: no network and no database. The steps, in order, are validate, drop duplicates,
exclude forecasts published after their target, then count gaps.
"""

from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from app.ingestion.records import (
    Actual,
    Forecast,
    MalformedRecordError,
    parse_actual,
    parse_forecast,
)
from app.ingestion.window import IngestionWindow

HOUR = timedelta(hours=1)
HALF_HOUR = timedelta(minutes=30)


@dataclass(frozen=True)
class ValidationSummary:
    forecast_rows_received: int
    forecast_rows_malformed: int
    forecast_duplicates_removed: int
    excluded_forecasts: int
    forecast_gap_hours: int
    actual_rows_received: int
    actual_rows_malformed: int
    actual_duplicates_removed: int
    actual_gap_periods: int


@dataclass(frozen=True)
class SnapshotData:
    forecasts: tuple[Forecast, ...]
    actuals: tuple[Actual, ...]
    summary: ValidationSummary
    window: IngestionWindow
    ingested_at: datetime


def build_snapshot(
    windfor_rows: Iterable[object],
    fuelhh_rows: Iterable[object],
    window: IngestionWindow,
    ingested_at: datetime,
) -> SnapshotData:
    """Clean both datasets and summarise what was dropped and what is missing."""
    windfor_rows = list(windfor_rows)
    fuelhh_rows = list(fuelhh_rows)

    valid_forecasts, forecast_malformed, forecast_duplicates = _clean(
        windfor_rows,
        parse_forecast,
        key=lambda f: (f.publish_time, f.target_time),
    )
    kept_forecasts = [f for f in valid_forecasts if f.publish_time <= f.target_time]
    excluded = len(valid_forecasts) - len(kept_forecasts)

    valid_actuals, actual_malformed, actual_duplicates = _clean(
        fuelhh_rows,
        parse_actual,
        key=lambda a: a.target_time,
    )

    forecasts = tuple(sorted(kept_forecasts, key=lambda f: (f.publish_time, f.target_time)))
    actuals = tuple(sorted(valid_actuals, key=lambda a: a.target_time))

    summary = ValidationSummary(
        forecast_rows_received=len(windfor_rows),
        forecast_rows_malformed=forecast_malformed,
        forecast_duplicates_removed=forecast_duplicates,
        excluded_forecasts=excluded,
        forecast_gap_hours=_forecast_gap_hours(forecasts),
        actual_rows_received=len(fuelhh_rows),
        actual_rows_malformed=actual_malformed,
        actual_duplicates_removed=actual_duplicates,
        actual_gap_periods=_actual_gap_periods(actuals, window),
    )
    return SnapshotData(
        forecasts=forecasts,
        actuals=actuals,
        summary=summary,
        window=window,
        ingested_at=ingested_at,
    )


def _clean[T](
    rows: list[object],
    parse: Callable[[object], T],
    key: Callable[[T], Hashable],
) -> tuple[list[T], int, int]:
    """Return ``(records, malformed count, duplicate count)``. The first copy of a key wins."""
    records: list[T] = []
    seen: set[Hashable] = set()
    malformed = 0
    duplicates = 0
    for raw in rows:
        try:
            record = parse(raw)
        except MalformedRecordError:
            malformed += 1
            continue
        record_key = key(record)
        if record_key in seen:
            duplicates += 1
            continue
        seen.add(record_key)
        records.append(record)
    return records, malformed, duplicates


def _forecast_gap_hours(forecasts: tuple[Forecast, ...]) -> int:
    """Hours between the first and last target time that have no forecast at all."""
    if not forecasts:
        return 0
    targets = {f.target_time for f in forecasts}
    first = min(targets)
    last = max(targets)
    expected_hours = (last - first) // HOUR + 1
    return expected_hours - len(targets)


def _actual_gap_periods(actuals: tuple[Actual, ...], window: IngestionWindow) -> int:
    """Half-hours in the settlement window with no actual value."""
    start = datetime.combine(window.fuelhh_settlement_from, time(0))
    end = datetime.combine(window.fuelhh_settlement_to + timedelta(days=1), time(0))
    expected = (end - start) // HALF_HOUR
    present = len({a.target_time for a in actuals if start <= a.target_time < end})
    return expected - present
