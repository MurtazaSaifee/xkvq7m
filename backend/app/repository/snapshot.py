"""Read-only access to the DuckDB snapshot. The only module that queries the snapshot.

Each call opens the file read-only and closes it again, so nothing holds the file between requests.
Coverage is returned as timezone-aware UTC. The decision methods use naive UTC, as the domain does;
the API adds the offset when it responds.
"""

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from app.domain.decision import DecisionForecast, HalfHourActual


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

    @contextmanager
    def _connection(self) -> Generator[duckdb.DuckDBPyConnection]:
        if not self._path.is_file():
            raise SnapshotUnavailableError(f"no snapshot at {self._path}")
        con = duckdb.connect(str(self._path), read_only=True)
        try:
            yield con
        except duckdb.CatalogException as error:
            raise SnapshotUnavailableError(str(error)) from error
        finally:
            con.close()

    def coverage(self) -> SnapshotCoverage:
        with self._connection() as con:
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

    def delivery_days(self) -> tuple[date, date]:
        """The first and last delivery day in scope, from the ingestion window."""
        with self._connection() as con:
            row = con.execute(
                "SELECT delivery_day_first, delivery_day_last FROM ingestion_metadata"
            ).fetchone()
        if row is None:
            raise SnapshotUnavailableError("snapshot has no ingestion metadata")
        return row[0], row[1]

    def decision_forecasts(
        self, target_times: Sequence[datetime], cutoff_time: datetime
    ) -> list[DecisionForecast]:
        """For each target time, the latest forecast published at or before ``cutoff_time``.

        This is the decision-forecast rule as one ASOF join. Targets with no forecast published
        before the cutoff are left out of the result.
        """
        with self._connection() as con:
            rows = con.execute(
                """
                SELECT t.target_time, f.publish_time, f.generation_mw
                FROM (SELECT unnest(?) AS target_time, ? AS cutoff_time) AS t
                ASOF LEFT JOIN forecasts AS f
                  ON f.target_time = t.target_time AND t.cutoff_time >= f.publish_time
                """,
                [list(target_times), cutoff_time],
            ).fetchall()
        return [
            DecisionForecast(
                target_time=target,
                publish_time=publish,
                generation_mw=float(generation),
            )
            for target, publish, generation in rows
            if publish is not None
        ]

    def actuals_between(self, start: datetime, end: datetime) -> list[HalfHourActual]:
        """Actual generation for target times in ``[start, end)``, in time order."""
        with self._connection() as con:
            rows = con.execute(
                "SELECT target_time, generation_mw FROM actuals "
                "WHERE target_time >= ? AND target_time < ? ORDER BY target_time",
                [start, end],
            ).fetchall()
        return [HalfHourActual(target_time=t, generation_mw=float(mw)) for t, mw in rows]
