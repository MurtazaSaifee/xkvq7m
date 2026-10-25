"""Hourly alignment and forecast error. Forecasts are hourly; actuals are half-hourly.

Pure functions only. The actual for hour *h* is the mean of the half-hours starting at *h*:00 and
*h*:30. If either half-hour is missing, the hour has no actual.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta

HALF_HOUR = timedelta(minutes=30)


def hourly_actual(hour_start: datetime, half_hours: Mapping[datetime, float]) -> float | None:
    """Mean generation over the hour starting at ``hour_start``, or ``None`` if a half-hour is missing."""
    first = half_hours.get(hour_start)
    second = half_hours.get(hour_start + HALF_HOUR)
    if first is None or second is None:
        return None
    return (first + second) / 2


def forecast_error(forecast_mw: float | None, actual_mw: float | None) -> float | None:
    """Forecast minus actual in MW. Positive means wind was over-forecast."""
    if forecast_mw is None or actual_mw is None:
        return None
    return forecast_mw - actual_mw
