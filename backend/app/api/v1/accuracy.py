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
    ACCURACY_FIRST_DAY,
    ACCURACY_LAST_DAY,
    ERROR_BIN_WIDTH_MW,
    AccuracyReport,
    accuracy_window,
    build_accuracy_report,
    decision_targets,
)
from app.domain.decision import CUTOFF_PATTERN, DEFAULT_CUTOFF, parse_cutoff
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


class AccuracyResponse(BaseModel):
    cutoff: str
    delivery_days: DeliveryDayRangeResponse
    summary: AccuracySummaryResponse
    histogram: ErrorHistogramResponse


def _to_response(report: AccuracyReport) -> AccuracyResponse:
    summary = report.summary
    return AccuracyResponse(
        cutoff=report.cutoff.strftime("%H:%M"),
        delivery_days=DeliveryDayRangeResponse(first=ACCURACY_FIRST_DAY, last=ACCURACY_LAST_DAY),
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
        window_start, window_end = accuracy_window()
        forecasts = repository.decision_forecasts_at(decision_targets(cutoff_time))
        actuals = repository.actuals_between(window_start, window_end)
    except SnapshotUnavailableError as error:
        raise ProblemError(
            503, "Service Unavailable", "Data snapshot is not available", ABOUT_BLANK
        ) from error

    return _to_response(build_accuracy_report(cutoff_time, forecasts, actuals))
