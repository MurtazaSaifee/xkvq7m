"""Accuracy metrics for decision forecasts over the Accuracy view's delivery days.

Pure functions only: no database, no HTTP. Metrics are computed on the hourly grid, one pair per
target hour: the decision forecast and the hourly actual, both in MW. A hour counts only when both
sides exist. Every other hour is excluded and counted by reason, so nothing is dropped silently.

Errors are forecast minus actual in MW, so a positive error means wind was over-forecast.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import numpy as np
from numpy.typing import NDArray

from app.domain.alignment import HALF_HOUR, top_of_hour_actual
from app.domain.decision import (
    DecisionForecast,
    DecisionSnapshot,
    HalfHourActual,
    build_decision_snapshot,
    decision_cutoff_instant,
    delivery_day_half_hours,
    delivery_day_hours,
)

# Histogram bins are fixed-width, so two cutoffs compare bin for bin. Edges fall on multiples of the
# width, which keeps the bins the same whatever the data. A 500 MW bin is about 1% of the typical
# national wind generation, which is fine enough to see the shape of the error without noise.
ERROR_BIN_WIDTH_MW = 500


@dataclass(frozen=True)
class AccuracySummary:
    target_hours: int
    measured_hours: int
    excluded_no_decision_forecast: int
    excluded_no_actual: int
    mae_mw: float | None
    bias_mw: float | None
    rmse_mw: float | None
    p90_abs_error_mw: float | None
    mean_actual_mw: float | None
    nmae_percent: float | None


@dataclass(frozen=True)
class ErrorBin:
    """One histogram bin. The lower edge is included and the upper edge excluded, except for the
    last bin, which includes its upper edge so the largest error is counted."""

    lower_mw: float
    upper_mw: float
    count: int


@dataclass(frozen=True)
class AccuracyReport:
    first_day: date
    last_day: date
    cutoff: time
    summary: AccuracySummary
    histogram: list[ErrorBin]


def delivery_days_between(first: date, last: date) -> list[date]:
    """Every delivery day from ``first`` to ``last`` inclusive. The scope comes from the caller."""
    count = (last - first).days + 1
    return [first + timedelta(days=offset) for offset in range(count)]


def _require_days(days: Sequence[date]) -> None:
    if not days:
        raise ValueError("at least one delivery day is needed")


def accuracy_window(days: Sequence[date]) -> tuple[datetime, datetime]:
    """The half-hourly actuals needed for ``days``, as ``[start, end)`` in naive UTC."""
    _require_days(days)
    first = delivery_day_half_hours(days[0])[0]
    last = delivery_day_half_hours(days[-1])[-1]
    return first, last + HALF_HOUR


def decision_targets(days: Sequence[date], cutoff: time) -> list[tuple[datetime, datetime]]:
    """Every target hour of ``days``, paired with the decision cutoff of its own delivery day."""
    return [
        (hour, decision_cutoff_instant(day, cutoff))
        for day in days
        for hour in delivery_day_hours(day)
    ]


@dataclass(frozen=True)
class AlignmentSensitivity:
    """Headline metrics under the two alignment rules, over the same decision forecasts.

    ``hourly_mean`` is the rule the headline figures use: the mean of the two half-hours.
    ``top_of_hour`` compares each hour with the half-hour starting at h:00 alone. Each side measures
    the hours its own rule can measure, so the two ``measured_hours`` can differ.
    """

    hourly_mean: AccuracySummary
    top_of_hour: AccuracySummary


def _day_snapshots(
    days: Sequence[date],
    cutoff: time,
    forecasts: Iterable[DecisionForecast],
    actuals: Iterable[HalfHourActual],
) -> list[DecisionSnapshot]:
    """One decision snapshot per delivery day, built by ``build_decision_snapshot``.

    The decision-forecast rule and the hourly alignment are the ones in ``app.domain.decision``, not
    a second copy, so every figure in this module agrees with the Decision view.
    """
    _require_days(days)
    day_of_target = {hour: day for day in days for hour in delivery_day_hours(day)}
    forecasts_by_day: dict[date, list[DecisionForecast]] = {day: [] for day in days}
    for forecast in forecasts:
        day = day_of_target.get(forecast.target_time)
        if day is not None:
            forecasts_by_day[day].append(forecast)

    actual_list = list(actuals)
    return [
        build_decision_snapshot(day, cutoff, forecasts_by_day[day], actual_list) for day in days
    ]


def build_accuracy_report(
    days: Sequence[date],
    cutoff: time,
    forecasts: Iterable[DecisionForecast],
    actuals: Iterable[HalfHourActual],
) -> AccuracyReport:
    """Accuracy over ``days``, from the same per-day snapshots the Decision view uses."""
    forecast_mw: list[float | None] = []
    actual_mw: list[float | None] = []
    for snapshot in _day_snapshots(days, cutoff, forecasts, actuals):
        for hour in snapshot.hours:
            forecast_mw.append(hour.forecast_mw)
            actual_mw.append(hour.actual_mw)

    return AccuracyReport(
        first_day=days[0],
        last_day=days[-1],
        cutoff=cutoff,
        summary=summarise_accuracy(forecast_mw, actual_mw),
        histogram=error_histogram(forecast_mw, actual_mw),
    )


def alignment_sensitivity(
    days: Sequence[date],
    cutoff: time,
    forecasts: Iterable[DecisionForecast],
    actuals: Iterable[HalfHourActual],
) -> AlignmentSensitivity:
    """Headline metrics under the hourly-mean rule and the top-of-hour rule, for the same forecasts.

    The decision forecasts are selected once, by the same rule as the report. Only the actual
    changes between the two sides.
    """
    forecast_mw: list[float | None] = []
    hourly_mw: list[float | None] = []
    top_mw: list[float | None] = []
    for snapshot in _day_snapshots(days, cutoff, forecasts, actuals):
        half_hours = {
            half.target_time: half.generation_mw
            for half in snapshot.actuals
            if half.generation_mw is not None
        }
        for hour in snapshot.hours:
            forecast_mw.append(hour.forecast_mw)
            hourly_mw.append(hour.actual_mw)
            top_mw.append(top_of_hour_actual(hour.hour_start, half_hours))

    return AlignmentSensitivity(
        hourly_mean=summarise_accuracy(forecast_mw, hourly_mw),
        top_of_hour=summarise_accuracy(forecast_mw, top_mw),
    )


def _measured_errors(
    forecast_mw: Sequence[float | None], actual_mw: Sequence[float | None]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Forecast and actual for the hours where both exist, as arrays of equal length."""
    if len(forecast_mw) != len(actual_mw):
        raise ValueError("forecast and actual must have one entry per target hour")
    pairs = [
        (forecast, actual)
        for forecast, actual in zip(forecast_mw, actual_mw, strict=True)
        if forecast is not None and actual is not None
    ]
    forecast = np.array([f for f, _ in pairs], dtype=np.float64)
    actual = np.array([a for _, a in pairs], dtype=np.float64)
    return forecast, actual


def summarise_accuracy(
    forecast_mw: Sequence[float | None], actual_mw: Sequence[float | None]
) -> AccuracySummary:
    """Headline metrics over the measured hours, with the excluded hours counted by reason.

    MAE is the mean absolute error. Bias is the mean error, so it shows direction. RMSE weights
    large misses more. P90 absolute error is the 90th percentile of the absolute error, read as
    "nine times out of ten the miss is under this". nMAE is MAE as a percentage of the mean actual.
    MAPE is not computed because it blows up when wind is near zero.
    """
    if len(forecast_mw) != len(actual_mw):
        raise ValueError("forecast and actual must have one entry per target hour")

    excluded_no_forecast = sum(1 for forecast in forecast_mw if forecast is None)
    excluded_no_actual = sum(
        1
        for forecast, actual in zip(forecast_mw, actual_mw, strict=True)
        if forecast is not None and actual is None
    )
    forecast, actual = _measured_errors(forecast_mw, actual_mw)
    measured = int(forecast.size)
    counts = {
        "target_hours": len(forecast_mw),
        "measured_hours": measured,
        "excluded_no_decision_forecast": excluded_no_forecast,
        "excluded_no_actual": excluded_no_actual,
    }
    if measured == 0:
        return AccuracySummary(
            **counts,
            mae_mw=None,
            bias_mw=None,
            rmse_mw=None,
            p90_abs_error_mw=None,
            mean_actual_mw=None,
            nmae_percent=None,
        )

    errors = forecast - actual
    absolute = np.abs(errors)
    mae = float(absolute.mean())
    mean_actual = float(actual.mean())
    return AccuracySummary(
        **counts,
        mae_mw=mae,
        bias_mw=float(errors.mean()),
        rmse_mw=float(math.sqrt(float(np.mean(errors**2)))),
        p90_abs_error_mw=float(np.percentile(absolute, 90)),
        mean_actual_mw=mean_actual,
        nmae_percent=None if mean_actual == 0 else mae / mean_actual * 100,
    )


def error_histogram(
    forecast_mw: Sequence[float | None],
    actual_mw: Sequence[float | None],
    bin_width_mw: int = ERROR_BIN_WIDTH_MW,
) -> list[ErrorBin]:
    """Counts of measured hours per fixed-width error bin, with edges on multiples of the width.

    The bins run from the lowest error's bin to the highest error's bin, so every bin in between is
    listed, even when empty. With no measured hour there are no bins.
    """
    forecast, actual = _measured_errors(forecast_mw, actual_mw)
    if forecast.size == 0:
        return []
    errors = forecast - actual

    width = float(bin_width_mw)
    lower = math.floor(float(errors.min()) / width) * width
    upper = math.ceil(float(errors.max()) / width) * width
    upper = max(upper, lower + width)
    bin_count = round((upper - lower) / width)
    edges = lower + width * np.arange(bin_count + 1, dtype=np.float64)
    counts, _ = np.histogram(errors, bins=edges)
    return [
        ErrorBin(lower_mw=float(edges[index]), upper_mw=float(edges[index + 1]), count=int(count))
        for index, count in enumerate(counts)
    ]
