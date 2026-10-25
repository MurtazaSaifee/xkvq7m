"""Forecast error by delivery day and UK hour of day, and the worst delivery days by energy error.

Both read the decision snapshot of each delivery day, so they use the decision-forecast rule and the
hourly alignment in ``app.domain.decision`` rather than a copy of them. Errors are forecast minus
actual in MW (or MWh for a day), so a positive error means wind was over-forecast.

Pure functions only: no database, no HTTP.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from app.domain.decision import (
    UK_TIMEZONE,
    DecisionForecast,
    HalfHourActual,
    build_decision_snapshot,
    delivery_day_hours,
)

# The worst-days table lists this many delivery days.
WORST_DAY_COUNT = 5


@dataclass(frozen=True)
class HeatmapCell:
    """The decision forecast error for one delivery day and one UK hour of day (0 to 23).

    ``error_mw`` is ``None`` where that hour cannot be measured.
    """

    delivery_day: date
    hour: int
    error_mw: float | None


@dataclass(frozen=True)
class WorstDay:
    """A delivery day ranked by the absolute value of its energy error over the measured hours."""

    delivery_day: date
    error_mwh: float
    forecast_mwh: float
    actual_mwh: float
    paired_hours: int


@dataclass(frozen=True)
class ErrorGrid:
    heatmap: list[HeatmapCell]
    worst_days: list[WorstDay]


def _uk_hour(hour_start: datetime) -> int:
    """The UK clock hour a naive UTC instant falls in."""
    return hour_start.replace(tzinfo=UTC).astimezone(UK_TIMEZONE).hour


def build_error_grid(
    days: Sequence[date],
    cutoff: time,
    forecasts: Iterable[DecisionForecast],
    actuals: Iterable[HalfHourActual],
    worst_count: int = WORST_DAY_COUNT,
) -> ErrorGrid:
    """The heatmap and the worst days for ``days`` at ``cutoff``.

    The worst days are the ``worst_count`` delivery days with the largest absolute energy error.
    Ties go to the earlier day. A day with no measured hour has no energy error, so it is not ranked.
    """
    day_of_target = {hour: day for day in days for hour in delivery_day_hours(day)}
    forecasts_by_day: dict[date, list[DecisionForecast]] = {day: [] for day in days}
    for forecast in forecasts:
        day = day_of_target.get(forecast.target_time)
        if day is not None:
            forecasts_by_day[day].append(forecast)

    actual_list = list(actuals)
    cells: list[HeatmapCell] = []
    ranked: list[WorstDay] = []
    for day in days:
        snapshot = build_decision_snapshot(day, cutoff, forecasts_by_day[day], actual_list)
        for hour in snapshot.hours:
            cells.append(
                HeatmapCell(
                    delivery_day=day,
                    hour=_uk_hour(hour.hour_start),
                    error_mw=hour.error_mw,
                )
            )
        kpis = snapshot.kpis
        if (
            kpis.forecast_mwh is not None
            and kpis.actual_mwh is not None
            and kpis.error_mwh is not None
        ):
            ranked.append(
                WorstDay(
                    delivery_day=day,
                    error_mwh=kpis.error_mwh,
                    forecast_mwh=kpis.forecast_mwh,
                    actual_mwh=kpis.actual_mwh,
                    paired_hours=kpis.paired_hours,
                )
            )

    ranked.sort(key=lambda worst: (-abs(worst.error_mwh), worst.delivery_day))
    return ErrorGrid(heatmap=cells, worst_days=ranked[:worst_count])
