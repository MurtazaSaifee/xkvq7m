"""Read-only access to the DuckDB snapshot. The only module that queries the snapshot.

Each call opens the file read-only and closes it again, so nothing holds the file between requests.
Coverage is returned as timezone-aware UTC. The decision methods use naive UTC, as the domain does;
the API adds the offset when it responds.
"""

import tempfile
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import duckdb
import numpy as np
from numpy.typing import NDArray

from app.domain.decision import DecisionForecast, HalfHourActual
from app.domain.horizon import ForecastColumns


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

        # Vercel's bundle is read-only and only the temp dir is writable, so DuckDB must not spill
        # or write its home-directory state beside the snapshot.
        scratch = tempfile.gettempdir()
        con = duckdb.connect(
            str(self._path),
            read_only=True,
            config={"temp_directory": scratch, "home_directory": scratch},
        )
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
        return self.decision_forecasts_at([(target, cutoff_time) for target in target_times])

    def decision_forecasts_at(
        self, targets: Sequence[tuple[datetime, datetime]]
    ) -> list[DecisionForecast]:
        """As ``decision_forecasts``, but each target has its own cutoff.

        ``targets`` holds (target time, cutoff time) pairs. Several delivery days share one query
        this way, since each day's cutoff falls on its own decision day.
        """
        if not targets:
            return []
        with self._connection() as con:
            rows = con.execute(
                """
                SELECT t.target_time, f.publish_time, f.generation_mw
                FROM (
                    SELECT unnest(?::TIMESTAMP[]) AS target_time,
                           unnest(?::TIMESTAMP[]) AS cutoff_time
                ) AS t
                ASOF LEFT JOIN forecasts AS f
                  ON f.target_time = t.target_time AND t.cutoff_time >= f.publish_time
                """,
                [[target for target, _ in targets], [cutoff for _, cutoff in targets]],
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

    def forecasts_between(self, start: datetime, end: datetime) -> ForecastColumns:
        """Every forecast whose target time is in ``[start, end)``, as columns, not one per run.

        Returned as numpy arrays straight from DuckDB, so the horizon analysis never builds a Python
        object per row.
        """
        with self._connection() as con:
            result = con.execute(
                "SELECT target_time, publish_time, generation_mw FROM forecasts "
                "WHERE target_time >= ? AND target_time < ?",
                [start, end],
            )
            # The duckdb package ships no type stubs, so fetchnumpy's return type is unknown here.
            columns = cast(
                "dict[str, NDArray[Any]]",
                result.fetchnumpy(),  # pyright: ignore[reportUnknownMemberType]
            )
        return ForecastColumns(
            target_time=np.asarray(columns["target_time"], dtype="datetime64[us]"),
            publish_time=np.asarray(columns["publish_time"], dtype="datetime64[us]"),
            generation_mw=np.asarray(columns["generation_mw"], dtype=np.float64),
        )

    def actuals_between(self, start: datetime, end: datetime) -> list[HalfHourActual]:
        """Actual generation for target times in ``[start, end)``, in time order."""
        with self._connection() as con:
            rows = con.execute(
                "SELECT target_time, generation_mw FROM actuals "
                "WHERE target_time >= ? AND target_time < ? ORDER BY target_time",
                [start, end],
            ).fetchall()
        return [HalfHourActual(target_time=t, generation_mw=float(mw)) for t, mw in rows]
