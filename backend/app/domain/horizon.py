"""Forecast error by horizon: how far ahead of its target time a forecast was published.

Pure functions only: no database, no HTTP. Every forecast whose target time is in scope counts, not
only the decision forecasts, so each bucket draws on everything the snapshot holds for that horizon.

The horizon of a forecast is its target time minus its publish time, in hours. Bucket k holds the
horizons in (k-1, k] hours, so 0.5 h is in bucket 1 and 1.5 h is in bucket 2. A horizon of exactly
zero, published at its own target time, has no interval of its own and joins bucket 1.

Errors are forecast minus actual in MW, as everywhere else. The actual for each hour comes from
``app.domain.alignment``. A forecast whose hour has no actual is left out and counted.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from numpy.typing import NDArray

from app.domain.alignment import hourly_actual
from app.domain.decision import HOUR, DecisionForecast, HalfHourActual

_SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class ForecastColumns:
    """Every forecast in a window as parallel arrays. Times are naive UTC, as in the snapshot."""

    target_time: NDArray[np.datetime64]
    publish_time: NDArray[np.datetime64]
    generation_mw: NDArray[np.float64]


@dataclass(frozen=True)
class HorizonBucket:
    """Forecasts whose horizon is in (lower_hours, upper_hours]. Metrics are None with no sample."""

    lower_hours: int
    upper_hours: int
    mae_mw: float | None
    bias_mw: float | None
    sample_count: int


@dataclass(frozen=True)
class HorizonRange:
    min_hours: float
    max_hours: float


@dataclass(frozen=True)
class HorizonCurve:
    buckets: list[HorizonBucket]
    excluded_no_actual: int
    decision_range: HorizonRange | None


def horizon_buckets(horizon_seconds: NDArray[np.int64]) -> NDArray[np.int64]:
    """The bucket of each horizon, given in whole seconds. Bucket k holds (k-1, k] hours."""
    if np.any(horizon_seconds < 0):
        raise ValueError("a forecast cannot be published after its target time")
    # Ceiling division in whole seconds, so a horizon of exactly k hours lands in bucket k.
    hours_up = -((-horizon_seconds) // _SECONDS_PER_HOUR)
    return np.maximum(hours_up, 1)


def hourly_actuals(
    window_start: datetime, window_end: datetime, actuals: Iterable[HalfHourActual]
) -> NDArray[np.float64]:
    """The actual for each hour in ``[window_start, window_end)``, NaN where it is missing."""
    half_hours = {a.target_time: a.generation_mw for a in actuals if a.generation_mw is not None}
    hour_count = (window_end - window_start) // HOUR
    values = [hourly_actual(window_start + HOUR * index, half_hours) for index in range(hour_count)]
    return np.array([np.nan if value is None else value for value in values], dtype=np.float64)


def decision_horizon_range(forecasts: Sequence[DecisionForecast]) -> HorizonRange | None:
    """The shortest and longest horizon among the decision forecasts, in hours."""
    if not forecasts:
        return None
    hours = [
        (f.target_time - f.publish_time).total_seconds() / _SECONDS_PER_HOUR for f in forecasts
    ]
    return HorizonRange(min_hours=min(hours), max_hours=max(hours))


def error_by_horizon(
    window_start: datetime,
    window_end: datetime,
    forecasts: ForecastColumns,
    actuals: Iterable[HalfHourActual],
    decision_forecasts: Sequence[DecisionForecast],
) -> HorizonCurve:
    """MAE, bias and sample count per horizon bucket, over every forecast in the window.

    Buckets run from 1 hour up to the longest horizon present, so the curve has no gaps at the top.
    A bucket with no measured forecast reports None for its metrics and a sample count of zero.
    """
    hourly = hourly_actuals(window_start, window_end, actuals)
    hour_index = (forecasts.target_time - np.datetime64(window_start)) // np.timedelta64(1, "h")
    if hour_index.size and (hour_index.min() < 0 or hour_index.max() >= hourly.size):
        raise ValueError("every forecast target must fall inside the window")
    horizon_seconds = (forecasts.target_time - forecasts.publish_time) // np.timedelta64(1, "s")
    buckets_of_row = horizon_buckets(horizon_seconds.astype(np.int64))
    decision_range = decision_horizon_range(decision_forecasts)

    actual = hourly[hour_index.astype(np.int64)]
    measured = ~np.isnan(actual)
    excluded = int(np.count_nonzero(~measured))
    if buckets_of_row.size == 0:
        return HorizonCurve(buckets=[], excluded_no_actual=0, decision_range=decision_range)

    error = forecasts.generation_mw - actual
    top = int(buckets_of_row.max())
    measured_buckets = buckets_of_row[measured]
    measured_errors = error[measured]
    counts = np.bincount(measured_buckets, minlength=top + 1)
    absolute_sums = np.bincount(
        measured_buckets, weights=np.abs(measured_errors), minlength=top + 1
    )
    error_sums = np.bincount(measured_buckets, weights=measured_errors, minlength=top + 1)

    buckets: list[HorizonBucket] = []
    for bucket in range(1, top + 1):
        count = int(counts[bucket])
        buckets.append(
            HorizonBucket(
                lower_hours=bucket - 1,
                upper_hours=bucket,
                mae_mw=float(absolute_sums[bucket] / count) if count else None,
                bias_mw=float(error_sums[bucket] / count) if count else None,
                sample_count=count,
            )
        )
    return HorizonCurve(buckets=buckets, excluded_no_actual=excluded, decision_range=decision_range)
