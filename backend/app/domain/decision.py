"""Decision-cutoff rule and the decision snapshot for one delivery day.

Pure functions only: no database, no HTTP. All datetimes here are naive UTC, matching the snapshot.
Delivery days and cutoffs are UK wall-clock times, so they are converted through Europe/London.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.alignment import HALF_HOUR, forecast_error, hourly_actual
from app.domain.kpis import DayKpis, day_kpis

DEFAULT_CUTOFF = time(9, 20)
UK_TIMEZONE = ZoneInfo("Europe/London")
CUTOFF_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
HOUR = timedelta(hours=1)
_CUTOFF_RE = re.compile(CUTOFF_PATTERN)


@dataclass(frozen=True)
class DecisionForecast:
    """A forecast for one target time, made at ``publish_time``."""

    target_time: datetime
    publish_time: datetime
    generation_mw: float


@dataclass(frozen=True)
class HalfHourActual:
    target_time: datetime
    generation_mw: float | None


@dataclass(frozen=True)
class DecisionHour:
    hour_start: datetime
    publish_time: datetime | None
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None


@dataclass(frozen=True)
class DecisionSnapshot:
    delivery_day: date
    decision_day: date
    cutoff: time
    cutoff_time: datetime
    forecast_run_publish_time: datetime | None
    hours: tuple[DecisionHour, ...]
    actuals: tuple[HalfHourActual, ...]
    kpis: DayKpis


def parse_cutoff(text: str) -> time:
    """Read a cutoff written as HH:MM. Anything else raises ``ValueError``."""
    if not _CUTOFF_RE.fullmatch(text):
        raise ValueError(f"cutoff must be HH:MM, got {text!r}")
    return time.fromisoformat(text)


def decision_cutoff_instant(delivery_day: date, cutoff: time) -> datetime:
    """The cutoff for ``delivery_day``: ``cutoff`` UK time on the day before, as naive UTC."""
    decision_day = delivery_day - timedelta(days=1)
    local = datetime.combine(decision_day, cutoff, tzinfo=UK_TIMEZONE)
    return local.astimezone(UTC).replace(tzinfo=None)


def _uk_midnight_utc(day: date) -> datetime:
    return datetime.combine(day, time(0), tzinfo=UK_TIMEZONE).astimezone(UTC).replace(tzinfo=None)


def _slots(day: date, step: timedelta) -> list[datetime]:
    """Start of each ``step`` in the UK day, as naive UTC. Clock-change days have 23 or 25 hours."""
    start = _uk_midnight_utc(day)
    end = _uk_midnight_utc(day + timedelta(days=1))
    return [start + step * index for index in range((end - start) // step)]


def delivery_day_hours(day: date) -> list[datetime]:
    return _slots(day, HOUR)


def delivery_day_half_hours(day: date) -> list[datetime]:
    return _slots(day, HALF_HOUR)


def build_decision_snapshot(
    delivery_day: date,
    cutoff: time,
    forecasts: Iterable[DecisionForecast],
    actuals: Iterable[HalfHourActual],
) -> DecisionSnapshot:
    """The decision snapshot for one delivery day, with hourly alignment and day KPIs.

    For each target time the decision forecast is the latest candidate published at or before the
    cutoff. A candidate published after the cutoff is ignored. A target with no such candidate is a
    gap.
    """
    cutoff_time = decision_cutoff_instant(delivery_day, cutoff)

    selected: dict[datetime, DecisionForecast] = {}
    for candidate in forecasts:
        if candidate.publish_time > cutoff_time:
            continue
        current = selected.get(candidate.target_time)
        if current is None or candidate.publish_time > current.publish_time:
            selected[candidate.target_time] = candidate

    half_hours = {a.target_time: a.generation_mw for a in actuals if a.generation_mw is not None}

    hours: list[DecisionHour] = []
    for hour_start in delivery_day_hours(delivery_day):
        chosen = selected.get(hour_start)
        forecast_mw = chosen.generation_mw if chosen is not None else None
        actual_mw = hourly_actual(hour_start, half_hours)
        hours.append(
            DecisionHour(
                hour_start=hour_start,
                publish_time=chosen.publish_time if chosen is not None else None,
                forecast_mw=forecast_mw,
                actual_mw=actual_mw,
                error_mw=forecast_error(forecast_mw, actual_mw),
            )
        )

    publish_times = [h.publish_time for h in hours if h.publish_time is not None]
    kpis = day_kpis(
        forecast_mw=[h.forecast_mw for h in hours],
        actual_mw=[h.actual_mw for h in hours],
    )
    return DecisionSnapshot(
        delivery_day=delivery_day,
        decision_day=delivery_day - timedelta(days=1),
        cutoff=cutoff,
        cutoff_time=cutoff_time,
        forecast_run_publish_time=max(publish_times) if publish_times else None,
        hours=tuple(hours),
        actuals=tuple(
            HalfHourActual(target_time=t, generation_mw=half_hours.get(t))
            for t in delivery_day_half_hours(delivery_day)
        ),
        kpis=kpis,
    )
