from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import AwareDatetime, BaseModel

from app.api.problems import (
    ABOUT_BLANK,
    INVALID_PARAMETER,
    PROBLEM_MEDIA_TYPE,
    ProblemDetail,
    ProblemError,
)
from app.core.config import snapshot_path
from app.domain.decision import (
    CUTOFF_PATTERN,
    DEFAULT_CUTOFF,
    DecisionSnapshot,
    build_decision_snapshot,
    decision_cutoff_instant,
    delivery_day_half_hours,
    delivery_day_hours,
    parse_cutoff,
)
from app.repository.snapshot import SnapshotRepository, SnapshotUnavailableError

router = APIRouter()

DELIVERY_DAY_OUT_OF_RANGE = "urn:wind-forecast:problem:delivery-day-out-of-range"
_PROBLEM_CONTENT: dict[str, Any] = {
    PROBLEM_MEDIA_TYPE: {"schema": ProblemDetail.model_json_schema()}
}
_PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"description": "Invalid or out-of-range parameters", "content": _PROBLEM_CONTENT},
    503: {"description": "The data snapshot is not available", "content": _PROBLEM_CONTENT},
}


class HourResponse(BaseModel):
    """One delivery hour: decision forecast, aligned actual and forecast error, all in MW."""

    target_time: AwareDatetime
    publish_time: AwareDatetime | None
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None


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


def _utc(value: datetime) -> datetime:
    """The domain works in naive UTC. The API states the offset explicitly."""
    return value.replace(tzinfo=UTC)


def _utc_or_none(value: datetime | None) -> datetime | None:
    return None if value is None else _utc(value)


def _to_response(snapshot: DecisionSnapshot) -> DecisionSnapshotResponse:
    return DecisionSnapshotResponse(
        delivery_day=snapshot.delivery_day,
        decision_day=snapshot.decision_day,
        cutoff=snapshot.cutoff.strftime("%H:%M"),
        cutoff_time=_utc(snapshot.cutoff_time),
        forecast_run_publish_time=_utc_or_none(snapshot.forecast_run_publish_time),
        hours=[
            HourResponse(
                target_time=_utc(hour.hour_start),
                publish_time=_utc_or_none(hour.publish_time),
                forecast_mw=hour.forecast_mw,
                actual_mw=hour.actual_mw,
                error_mw=hour.error_mw,
            )
            for hour in snapshot.hours
        ],
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
    )


@router.get(
    "/decision-snapshot",
    response_model=DecisionSnapshotResponse,
    summary="Decision snapshot for one delivery day, with day KPIs",
    responses=_PROBLEM_RESPONSES,
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
            raise ProblemError(422, "Invalid request", str(error), INVALID_PARAMETER) from error
        targets = delivery_day_hours(delivery_day)
        half_hours = delivery_day_half_hours(delivery_day)
        forecasts = repository.decision_forecasts(
            targets, decision_cutoff_instant(delivery_day, cutoff_time)
        )
        actuals = repository.actuals_between(half_hours[0], half_hours[-1] + timedelta(minutes=30))
    except SnapshotUnavailableError as error:
        raise ProblemError(
            503, "Service Unavailable", "Data snapshot is not available", ABOUT_BLANK
        ) from error

    snapshot = build_decision_snapshot(delivery_day, cutoff_time, forecasts, actuals)
    return _to_response(snapshot)
