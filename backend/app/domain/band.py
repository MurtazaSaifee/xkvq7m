"""The expected-error band: where actual generation is expected to fall, from past errors only.

For delivery day D, the band is the P10 and P90 of the hourly decision-forecast errors (forecast
minus actual, MW) over the BAND_LOOKBACK_DAYS delivery days before D, at the same cutoff. Only those
days are read, so the band never uses D or any later day. The percentiles pool every measured hour
of those days, not a mean per day.

Error is forecast minus actual, so actual = forecast - error. The band for the actual generation of
a decision forecast F is therefore [F - P90, F - P10].

Pure functions only: no database, no HTTP. Datetimes are naive UTC, as in ``app.domain.decision``.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time, timedelta

import numpy as np

from app.domain.decision import (
    DecisionForecast,
    DecisionSnapshot,
    HalfHourActual,
    build_decision_snapshot,
)

BAND_LOOKBACK_DAYS = 14
# A band needs errors from at least this many past delivery days. With fewer, the day gets no band.
BAND_MIN_HISTORY_DAYS = 7
LOWER_PERCENTILE = 10
UPPER_PERCENTILE = 90


@dataclass(frozen=True)
class ExpectedErrorBand:
    """The band for one delivery day: the P10 and P90 of past forecast errors, in MW."""

    lower_error_mw: float
    upper_error_mw: float
    history_days: int

    def actual_range_mw(self, forecast_mw: float | None) -> tuple[float | None, float | None]:
        """The range the actual generation is expected to fall in, given a decision forecast.

        Positive past errors (over-forecasts) push the range down, so the upper edge of the error
        gives the lower edge of the actual. No forecast gives no range.
        """
        if forecast_mw is None:
            return None, None
        return forecast_mw - self.upper_error_mw, forecast_mw - self.lower_error_mw


@dataclass(frozen=True)
class BandCoverage:
    """How often the actual generation fell inside its band, over a scope of delivery days.

    The counted hours are the hours with a decision forecast, an actual and a band. Every other hour
    is excluded and counted by reason, so the four counts add up to the target hours in scope.
    """

    counted_hours: int
    inside_hours: int
    excluded_no_band: int
    excluded_no_decision_forecast: int
    excluded_no_actual: int
    coverage_percent: float | None


def lookback_days(day: date) -> list[date]:
    """The delivery days the band for ``day`` may read: the fourteen before it, oldest first."""
    return [day - timedelta(days=offset) for offset in range(BAND_LOOKBACK_DAYS, 0, -1)]


def expected_error_band(
    day: date, errors_by_day: Mapping[date, Sequence[float]]
) -> ExpectedErrorBand | None:
    """The band for ``day`` from the measured hourly errors of its past delivery days.

    Only the lookback days are read, so errors for ``day`` or any later day in the mapping are
    ignored. A past day counts only if it has at least one measured error. If fewer than
    BAND_MIN_HISTORY_DAYS past days count, there is no band.
    """
    pooled: list[float] = []
    history_days = 0
    for past_day in lookback_days(day):
        errors = errors_by_day.get(past_day)
        if errors:
            pooled.extend(errors)
            history_days += 1
    if history_days < BAND_MIN_HISTORY_DAYS:
        return None

    lower, upper = np.percentile(
        np.asarray(pooled, dtype=np.float64), [LOWER_PERCENTILE, UPPER_PERCENTILE]
    )
    return ExpectedErrorBand(
        lower_error_mw=float(lower),
        upper_error_mw=float(upper),
        history_days=history_days,
    )


def _snapshots(
    days: Iterable[date],
    cutoff: time,
    forecasts: Iterable[DecisionForecast],
    actuals: Iterable[HalfHourActual],
) -> dict[date, DecisionSnapshot]:
    """The decision snapshot of each day, with the selection and alignment of the Decision view."""
    forecast_list = list(forecasts)
    actual_list = list(actuals)
    return {day: build_decision_snapshot(day, cutoff, forecast_list, actual_list) for day in days}


def _measured_errors(snapshot: DecisionSnapshot) -> list[float]:
    return [hour.error_mw for hour in snapshot.hours if hour.error_mw is not None]


def band_for_day(
    day: date,
    cutoff: time,
    forecasts: Iterable[DecisionForecast],
    actuals: Iterable[HalfHourActual],
) -> ExpectedErrorBand | None:
    """The band for ``day`` at ``cutoff``, built from the forecasts and actuals it is given.

    The inputs must cover the lookback days. Anything they hold for ``day`` or later is not read.
    """
    past = lookback_days(day)
    snapshots = _snapshots(past, cutoff, forecasts, actuals)
    return expected_error_band(day, {d: _measured_errors(s) for d, s in snapshots.items()})


def build_band_coverage(
    scope_days: Sequence[date],
    cutoff: time,
    forecasts: Iterable[DecisionForecast],
    actuals: Iterable[HalfHourActual],
) -> BandCoverage:
    """Band coverage over ``scope_days``, with each day's band built walk-forward from its own past.

    The inputs must cover the lookback days of every scope day, which is the warm-up for the
    earliest ones.
    """
    needed = sorted({past for day in scope_days for past in lookback_days(day)} | set(scope_days))
    snapshots = _snapshots(needed, cutoff, forecasts, actuals)
    errors_by_day = {d: _measured_errors(s) for d, s in snapshots.items()}

    counted = inside = excluded_no_band = excluded_no_forecast = excluded_no_actual = 0
    for day in scope_days:
        band = expected_error_band(day, errors_by_day)
        for hour in snapshots[day].hours:
            if hour.forecast_mw is None:
                excluded_no_forecast += 1
                continue
            if hour.actual_mw is None:
                excluded_no_actual += 1
                continue
            if band is None:
                excluded_no_band += 1
                continue
            low, high = band.actual_range_mw(hour.forecast_mw)
            counted += 1
            if low is not None and high is not None and low <= hour.actual_mw <= high:
                inside += 1

    return BandCoverage(
        counted_hours=counted,
        inside_hours=inside,
        excluded_no_band=excluded_no_band,
        excluded_no_decision_forecast=excluded_no_forecast,
        excluded_no_actual=excluded_no_actual,
        coverage_percent=None if counted == 0 else inside / counted * 100,
    )
