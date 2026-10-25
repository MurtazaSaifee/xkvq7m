"""Read-only access to the DuckDB snapshot. The only module that queries the snapshot.

Each call opens the file read-only and closes it again, so nothing holds the file between requests.
Timestamps are stored as naive UTC and returned as timezone-aware UTC.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb


class SnapshotUnavailableError(LookupError):
    """The snapshot file is missing, or it has no ingestion metadata."""


@dataclass(frozen=True)
class TargetCoverage:
    first_target_time: datetime | None
    last_target_time: datetime | None
    row_count: int


@dataclass(frozen=True)
class SnapshotCoverage:
    ingested_at: datetime
    forecasts: TargetCoverage
    actuals: TargetCoverage
    excluded_forecasts: int
    delivery_day_first: date
    delivery_day_last: date


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None else None


class SnapshotRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def coverage(self) -> SnapshotCoverage:
        if not self._path.is_file():
            raise SnapshotUnavailableError(f"no snapshot at {self._path}")

        con = duckdb.connect(str(self._path), read_only=True)
        try:
            metadata = con.execute(
                "SELECT ingested_at, excluded_forecasts, delivery_day_first, delivery_day_last "
                "FROM ingestion_metadata"
            ).fetchone()
            forecasts = con.execute(
                "SELECT min(target_time), max(target_time), count(*) FROM forecasts"
            ).fetchone()
            actuals = con.execute(
                "SELECT min(target_time), max(target_time), count(*) FROM actuals"
            ).fetchone()
        except duckdb.CatalogException as error:
            raise SnapshotUnavailableError(str(error)) from error
        finally:
            con.close()

        if metadata is None or forecasts is None or actuals is None:
            raise SnapshotUnavailableError("snapshot has no ingestion metadata")

        ingested_at, excluded, delivery_first, delivery_last = metadata
        return SnapshotCoverage(
            ingested_at=ingested_at.replace(tzinfo=UTC),
            forecasts=TargetCoverage(_utc(forecasts[0]), _utc(forecasts[1]), int(forecasts[2])),
            actuals=TargetCoverage(_utc(actuals[0]), _utc(actuals[1]), int(actuals[2])),
            excluded_forecasts=int(excluded),
            delivery_day_first=delivery_first,
            delivery_day_last=delivery_last,
        )
