"""Day KPIs: forecast MWh, actual MWh and forecast error for one delivery day.

Each element is one hour, so the sum of hourly MW is the energy in MWh. Only hours where both the
forecast and the actual exist are summed, so the three totals describe the same hours. Hours
missing either side are counted instead. Pure functions only.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DayKpis:
    forecast_mwh: float | None
    actual_mwh: float | None
    error_mwh: float | None
    paired_hours: int
    missing_forecast_hours: int
    missing_actual_hours: int


def day_kpis(forecast_mw: Sequence[float | None], actual_mw: Sequence[float | None]) -> DayKpis:
    """Totals over the hours where both sides are present. Hours are paired by position."""
    if len(forecast_mw) != len(actual_mw):
        raise ValueError("forecast and actual must have one entry per hour")

    paired = [
        (forecast, actual)
        for forecast, actual in zip(forecast_mw, actual_mw, strict=True)
        if forecast is not None and actual is not None
    ]
    missing_forecast = sum(1 for forecast in forecast_mw if forecast is None)
    missing_actual = sum(1 for actual in actual_mw if actual is None)

    if not paired:
        return DayKpis(None, None, None, 0, missing_forecast, missing_actual)

    forecast_total = sum(forecast for forecast, _ in paired)
    actual_total = sum(actual for _, actual in paired)
    return DayKpis(
        forecast_mwh=forecast_total,
        actual_mwh=actual_total,
        error_mwh=forecast_total - actual_total,
        paired_hours=len(paired),
        missing_forecast_hours=missing_forecast,
        missing_actual_hours=missing_actual,
    )
