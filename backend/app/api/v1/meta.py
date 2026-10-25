from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel

from app.core.config import snapshot_path
from app.repository.snapshot import SnapshotCoverage, SnapshotRepository, SnapshotUnavailableError

router = APIRouter()


class TargetCoverageResponse(BaseModel):
    first_target_time: AwareDatetime | None
    last_target_time: AwareDatetime | None
    row_count: int


class DeliveryDaysResponse(BaseModel):
    first: date
    last: date


class MetaResponse(BaseModel):
    ingested_at: AwareDatetime
    forecasts: TargetCoverageResponse
    actuals: TargetCoverageResponse
    excluded_forecasts: int
    delivery_days: DeliveryDaysResponse


def _to_response(coverage: SnapshotCoverage) -> MetaResponse:
    return MetaResponse(
        ingested_at=coverage.ingested_at,
        forecasts=TargetCoverageResponse(
            first_target_time=coverage.forecasts.first_target_time,
            last_target_time=coverage.forecasts.last_target_time,
            row_count=coverage.forecasts.row_count,
        ),
        actuals=TargetCoverageResponse(
            first_target_time=coverage.actuals.first_target_time,
            last_target_time=coverage.actuals.last_target_time,
            row_count=coverage.actuals.row_count,
        ),
        excluded_forecasts=coverage.excluded_forecasts,
        delivery_days=DeliveryDaysResponse(
            first=coverage.delivery_day_first,
            last=coverage.delivery_day_last,
        ),
    )


@router.get(
    "/meta", response_model=MetaResponse, summary="Snapshot coverage and ingestion metadata"
)
def meta() -> MetaResponse:
    try:
        coverage = SnapshotRepository(snapshot_path()).coverage()
    except SnapshotUnavailableError as error:
        raise HTTPException(status_code=503, detail="Data snapshot is not available") from error
    return _to_response(coverage)
