from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime, BaseModel

from app.api.cache import cache_immutable_answer
from app.api.problems import PROBLEM_RESPONSES, ProblemError, invalid_cutoff, snapshot_unavailable
from app.core.config import snapshot_path
from app.domain.accuracy import accuracy_window, decision_targets
from app.domain.band import ExpectedErrorBand, band_for_day, lookback_days
from app.domain.decision import (
    CUTOFF_PATTERN,
    DEFAULT_CUTOFF,
    DecisionHour,
    DecisionSnapshot,
    build_decision_snapshot,
    parse_cutoff,
)
from app.repository.snapshot import SnapshotRepository, SnapshotUnavailableError

router = APIRouter()

DELIVERY_DAY_OUT_OF_RANGE = "urn:wind-forecast:problem:delivery-day-out-of-range"


class HourResponse(BaseModel):
    """One delivery hour: decision forecast, aligned actual and forecast error, all in MW.

    The band range is where the actual is expected to fall, given the decision forecast. It is null
    when the hour has no decision forecast, or the day has no expected-error band.
    """

    target_time: AwareDatetime
    publish_time: AwareDatetime | None
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    band_low_mw: float | None
    band_high_mw: float | None


class ExpectedErrorBandResponse(BaseModel):
    """The band for the delivery day: P10 and P90 of the hourly decision-forecast errors (forecast
    minus actual, MW) over the 14 delivery days that end two days before it (D-15 to D-2), at the
    same cutoff. A band needs at least 7 of those days with measured errors."""

    lower_error_mw: float
    upper_error_mw: float
    history_days: int


class ActualResponse(BaseModel):
    target_time: AwareDatetime
    generation_mw: float | None


class KpisResponse(BaseModel):
    forecast_mwh: float | None
    actual_mwh: float | None
    error_mwh: float | None
    paired_hours: int
    missing_forecast_hours: int
    missing_actual_hours: int


class DecisionSnapshotResponse(BaseModel):
    delivery_day: date
    decision_day: date
    cutoff: str
    cutoff_time: AwareDatetime
    forecast_run_publish_time: AwareDatetime | None
    hours: list[HourResponse]
    actuals: list[ActualResponse]
    kpis: KpisResponse
    band: ExpectedErrorBandResponse | None


def _utc(value: datetime) -> datetime:
    """The domain works in naive UTC. The API states the offset explicitly."""
    return value.replace(tzinfo=UTC)


def _utc_or_none(value: datetime | None) -> datetime | None:
    return None if value is None else _utc(value)


def _band_response(band: ExpectedErrorBand | None) -> ExpectedErrorBandResponse | None:
    if band is None:
        return None
    return ExpectedErrorBandResponse(
        lower_error_mw=band.lower_error_mw,
        upper_error_mw=band.upper_error_mw,
        history_days=band.history_days,
    )


def _hour_response(hour: DecisionHour, band: ExpectedErrorBand | None) -> HourResponse:
    if band is None or hour.forecast_mw is None:
        band_low, band_high = None, None
    else:
        band_low, band_high = band.actual_range_mw(hour.forecast_mw)
    return HourResponse(
        target_time=_utc(hour.hour_start),
        publish_time=_utc_or_none(hour.publish_time),
        forecast_mw=hour.forecast_mw,
        actual_mw=hour.actual_mw,
        error_mw=hour.error_mw,
        band_low_mw=band_low,
        band_high_mw=band_high,
    )


def _to_response(
    snapshot: DecisionSnapshot, band: ExpectedErrorBand | None
) -> DecisionSnapshotResponse:
    return DecisionSnapshotResponse(
        delivery_day=snapshot.delivery_day,
        decision_day=snapshot.decision_day,
        cutoff=snapshot.cutoff.strftime("%H:%M"),
        cutoff_time=_utc(snapshot.cutoff_time),
        forecast_run_publish_time=_utc_or_none(snapshot.forecast_run_publish_time),
        hours=[_hour_response(hour, band) for hour in snapshot.hours],
        actuals=[
            ActualResponse(target_time=_utc(actual.target_time), generation_mw=actual.generation_mw)
            for actual in snapshot.actuals
        ],
        kpis=KpisResponse(
            forecast_mwh=snapshot.kpis.forecast_mwh,
            actual_mwh=snapshot.kpis.actual_mwh,
            error_mwh=snapshot.kpis.error_mwh,
            paired_hours=snapshot.kpis.paired_hours,
            missing_forecast_hours=snapshot.kpis.missing_forecast_hours,
            missing_actual_hours=snapshot.kpis.missing_actual_hours,
        ),
        band=_band_response(band),
    )


@router.get(
    "/decision-snapshot",
    response_model=DecisionSnapshotResponse,
    summary="Decision snapshot for one delivery day, with day KPIs",
    responses=PROBLEM_RESPONSES,
    dependencies=[Depends(cache_immutable_answer)],
)
def decision_snapshot(
    delivery_day: Annotated[
        date,
        Query(description="UK delivery day, YYYY-MM-DD, within the snapshot's delivery window."),
    ],
    cutoff: Annotated[
        str,
        Query(
            pattern=CUTOFF_PATTERN,
            description="Decision cutoff as HH:MM UK time on the decision day (the day before).",
        ),
    ] = DEFAULT_CUTOFF.strftime("%H:%M"),
) -> DecisionSnapshotResponse:
    try:
        repository = SnapshotRepository(snapshot_path())
        first_day, last_day = repository.delivery_days()
        if not first_day <= delivery_day <= last_day:
            raise ProblemError(
                422,
                "Delivery day out of range",
                f"delivery_day must be between {first_day.isoformat()} and {last_day.isoformat()}",
                DELIVERY_DAY_OUT_OF_RANGE,
            )

        try:
            cutoff_time = parse_cutoff(cutoff)
        except ValueError as error:
            raise invalid_cutoff(error) from error
        # The band reads the fourteen days that end two days before the delivery day, so their
        # forecasts and actuals are fetched too. The decision day itself is never read by the band.
        days = [*lookback_days(delivery_day), delivery_day]
        forecasts = repository.decision_forecasts_at(decision_targets(days, cutoff_time))
        actuals = repository.actuals_between(*accuracy_window(days))
    except SnapshotUnavailableError as error:
        raise snapshot_unavailable() from error

    snapshot = build_decision_snapshot(delivery_day, cutoff_time, forecasts, actuals)
    band = band_for_day(delivery_day, cutoff_time, forecasts, actuals)
    return _to_response(snapshot, band)
