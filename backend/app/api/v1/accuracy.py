from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.problems import (
    ABOUT_BLANK,
    INVALID_PARAMETER,
    PROBLEM_MEDIA_TYPE,
    ProblemDetail,
    ProblemError,
)
from app.core.config import snapshot_path
from app.domain.accuracy import (
    ERROR_BIN_WIDTH_MW,
    AccuracyReport,
    accuracy_window,
    build_accuracy_report,
    decision_targets,
    delivery_days_between,
)
from app.domain.decision import CUTOFF_PATTERN, DEFAULT_CUTOFF, parse_cutoff
from app.domain.horizon import HorizonCurve, HorizonRange, error_by_horizon
from app.repository.snapshot import SnapshotRepository, SnapshotUnavailableError

router = APIRouter()

_PROBLEM_CONTENT: dict[str, Any] = {
    PROBLEM_MEDIA_TYPE: {"schema": ProblemDetail.model_json_schema()}
}
_PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"description": "Invalid parameters", "content": _PROBLEM_CONTENT},
    503: {"description": "The data snapshot is not available", "content": _PROBLEM_CONTENT},
}


class DeliveryDayRangeResponse(BaseModel):
    first: date
    last: date


class AccuracySummaryResponse(BaseModel):
    """Headline metrics over the measured hours, in MW unless stated. Metrics are null when no
    hour can be measured. Excluded hours are counted by reason, so the three counts add up to
    ``target_hours``."""

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


class ErrorBinResponse(BaseModel):
    """One bin: the lower edge is included and the upper edge excluded, except for the last bin."""

    lower_mw: float
    upper_mw: float
    count: int


class ErrorHistogramResponse(BaseModel):
    bin_width_mw: int
    bins: list[ErrorBinResponse]


class HorizonBucketResponse(BaseModel):
    """Forecasts whose horizon is in (lower_hours, upper_hours]. MAE and bias are in MW and are null
    when the bucket has no measured forecast, in which case the sample count is zero."""

    lower_hours: int
    upper_hours: int
    mae_mw: float | None
    bias_mw: float | None
    sample_count: int


class HorizonRangeResponse(BaseModel):
    min_hours: float
    max_hours: float


class HorizonCurveResponse(BaseModel):
    """Error by forecast horizon over every forecast whose target time is in scope, not only the
    decision forecasts. Buckets are 1 hour wide, from 1 hour up to the longest horizon in scope.
    ``decision_horizon_range_hours`` is the shortest and longest horizon of the decision forecasts
    at the cutoff, so the curve can mark where the desk's decisions sit."""

    buckets: list[HorizonBucketResponse]
    excluded_no_actual: int
    decision_horizon_range_hours: HorizonRangeResponse | None


class AccuracyResponse(BaseModel):
    cutoff: str
    delivery_days: DeliveryDayRangeResponse
    summary: AccuracySummaryResponse
    histogram: ErrorHistogramResponse
    horizon_curve: HorizonCurveResponse


def _horizon_range_to_response(decision_range: HorizonRange | None) -> HorizonRangeResponse | None:
    if decision_range is None:
        return None
    return HorizonRangeResponse(
        min_hours=decision_range.min_hours, max_hours=decision_range.max_hours
    )


def _horizon_to_response(curve: HorizonCurve) -> HorizonCurveResponse:
    return HorizonCurveResponse(
        buckets=[
            HorizonBucketResponse(
                lower_hours=b.lower_hours,
                upper_hours=b.upper_hours,
                mae_mw=b.mae_mw,
                bias_mw=b.bias_mw,
                sample_count=b.sample_count,
            )
            for b in curve.buckets
        ],
        excluded_no_actual=curve.excluded_no_actual,
        decision_horizon_range_hours=_horizon_range_to_response(curve.decision_range),
    )


def _to_response(report: AccuracyReport, horizon: HorizonCurve) -> AccuracyResponse:
    summary = report.summary
    return AccuracyResponse(
        cutoff=report.cutoff.strftime("%H:%M"),
        delivery_days=DeliveryDayRangeResponse(first=report.first_day, last=report.last_day),
        summary=AccuracySummaryResponse(
            target_hours=summary.target_hours,
            measured_hours=summary.measured_hours,
            excluded_no_decision_forecast=summary.excluded_no_decision_forecast,
            excluded_no_actual=summary.excluded_no_actual,
            mae_mw=summary.mae_mw,
            bias_mw=summary.bias_mw,
            rmse_mw=summary.rmse_mw,
            p90_abs_error_mw=summary.p90_abs_error_mw,
            mean_actual_mw=summary.mean_actual_mw,
            nmae_percent=summary.nmae_percent,
        ),
        histogram=ErrorHistogramResponse(
            bin_width_mw=ERROR_BIN_WIDTH_MW,
            bins=[
                ErrorBinResponse(lower_mw=b.lower_mw, upper_mw=b.upper_mw, count=b.count)
                for b in report.histogram
            ],
        ),
        horizon_curve=_horizon_to_response(horizon),
    )


@router.get(
    "/accuracy",
    response_model=AccuracyResponse,
    summary="Accuracy of decision forecasts over the scope, with an error histogram",
    responses=_PROBLEM_RESPONSES,
)
def accuracy(
    cutoff: Annotated[
        str,
        Query(
            pattern=CUTOFF_PATTERN,
            description="Decision cutoff as HH:MM UK time on each decision day (the day before).",
        ),
    ] = DEFAULT_CUTOFF.strftime("%H:%M"),
) -> AccuracyResponse:
    try:
        cutoff_time = parse_cutoff(cutoff)
    except ValueError as error:
        raise ProblemError(422, "Invalid request", str(error), INVALID_PARAMETER) from error

    try:
        repository = SnapshotRepository(snapshot_path())
        first_day, last_day = repository.delivery_days()
        days = delivery_days_between(first_day, last_day)
        window_start, window_end = accuracy_window(days)
        forecasts = repository.decision_forecasts_at(decision_targets(days, cutoff_time))
        actuals = repository.actuals_between(window_start, window_end)
        all_forecasts = repository.forecasts_between(window_start, window_end)
    except SnapshotUnavailableError as error:
        raise ProblemError(
            503, "Service Unavailable", "Data snapshot is not available", ABOUT_BLANK
        ) from error

    report = build_accuracy_report(days, cutoff_time, forecasts, actuals)
    horizon = error_by_horizon(
        window_start, window_end, all_forecasts, actuals, decision_forecasts=forecasts
    )
    return _to_response(report, horizon)
