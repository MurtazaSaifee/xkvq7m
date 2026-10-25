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
from app.domain.band import (
    BAND_LOOKBACK_DAYS,
    BAND_MIN_HISTORY_DAYS,
    BandCoverage,
    build_band_coverage,
    lookback_days,
)
from app.domain.decision import CUTOFF_PATTERN, DEFAULT_CUTOFF, parse_cutoff
from app.domain.error_grid import ErrorGrid, build_error_grid
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


class BandCoverageResponse(BaseModel):
    """How often the actual fell inside its expected-error band over the scope. Hours are counted
    when they have a decision forecast, an actual and a band. The four counts add up to
    ``target_hours`` of the scope, and the coverage is null when no hour is counted."""

    lookback_days: int
    min_history_days: int
    counted_hours: int
    inside_hours: int
    coverage_percent: float | None
    excluded_no_band: int
    excluded_no_decision_forecast: int
    excluded_no_actual: int


class HeatmapCellResponse(BaseModel):
    """The decision forecast error for one delivery day and one UK hour of day (0 to 23), in MW.
    ``error_mw`` is null where that hour cannot be measured."""

    delivery_day: date
    hour: int
    error_mw: float | None


class ErrorHeatmapResponse(BaseModel):
    cells: list[HeatmapCellResponse]


class WorstDayResponse(BaseModel):
    """A delivery day ranked by the absolute value of its energy error. Energies are in MWh, and the
    error is forecast minus actual, so a positive error means wind was over-forecast."""

    delivery_day: date
    error_mwh: float
    forecast_mwh: float
    actual_mwh: float
    paired_hours: int


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
    band_coverage: BandCoverageResponse
    heatmap: ErrorHeatmapResponse
    worst_days: list[WorstDayResponse]
    horizon_curve: HorizonCurveResponse


def _band_coverage_response(coverage: BandCoverage) -> BandCoverageResponse:
    return BandCoverageResponse(
        lookback_days=BAND_LOOKBACK_DAYS,
        min_history_days=BAND_MIN_HISTORY_DAYS,
        counted_hours=coverage.counted_hours,
        inside_hours=coverage.inside_hours,
        coverage_percent=coverage.coverage_percent,
        excluded_no_band=coverage.excluded_no_band,
        excluded_no_decision_forecast=coverage.excluded_no_decision_forecast,
        excluded_no_actual=coverage.excluded_no_actual,
    )


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


def _to_response(
    report: AccuracyReport, grid: ErrorGrid, horizon: HorizonCurve, coverage: BandCoverage
) -> AccuracyResponse:
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
        band_coverage=_band_coverage_response(coverage),
        heatmap=ErrorHeatmapResponse(
            cells=[
                HeatmapCellResponse(
                    delivery_day=cell.delivery_day, hour=cell.hour, error_mw=cell.error_mw
                )
                for cell in grid.heatmap
            ]
        ),
        worst_days=[
            WorstDayResponse(
                delivery_day=worst.delivery_day,
                error_mwh=worst.error_mwh,
                forecast_mwh=worst.forecast_mwh,
                actual_mwh=worst.actual_mwh,
                paired_hours=worst.paired_hours,
            )
            for worst in grid.worst_days
        ],
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
        # The band's warm-up is the lookback of the first scope day, so those days are read too.
        # Only the band coverage uses them. The other figures still cover only the scope days.
        history = delivery_days_between(lookback_days(first_day)[0], last_day)
        history_start, history_end = accuracy_window(history)
        band_forecasts = repository.decision_forecasts_at(decision_targets(history, cutoff_time))
        band_actuals = repository.actuals_between(history_start, history_end)
    except SnapshotUnavailableError as error:
        raise ProblemError(
            503, "Service Unavailable", "Data snapshot is not available", ABOUT_BLANK
        ) from error

    report = build_accuracy_report(days, cutoff_time, forecasts, actuals)
    grid = build_error_grid(days, cutoff_time, forecasts, actuals)
    horizon = error_by_horizon(
        window_start, window_end, all_forecasts, actuals, decision_forecasts=forecasts
    )
    coverage = build_band_coverage(days, cutoff_time, band_forecasts, band_actuals)
    return _to_response(report, grid, horizon, coverage)
