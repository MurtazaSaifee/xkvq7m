"""Write a SnapshotData to a DuckDB file, built beside the target and renamed into place."""

import os
from datetime import UTC
from pathlib import Path

import duckdb

from app.ingestion.build import SnapshotData
from app.repository.schema import SCHEMA_STATEMENTS

SNAPSHOT_FILE_MODE = 0o444


def write_snapshot(snapshot: SnapshotData, path: Path) -> None:
    """Replace ``path`` with a new snapshot. A failed run leaves the previous file untouched."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.unlink(missing_ok=True)

    con = duckdb.connect(str(temp))
    try:
        for statement in SCHEMA_STATEMENTS:
            con.execute(statement)
        con.executemany(
            "INSERT INTO forecasts VALUES (?, ?, ?)",
            [(f.publish_time, f.target_time, f.generation_mw) for f in snapshot.forecasts],
        )
        con.executemany(
            "INSERT INTO actuals VALUES (?, ?)",
            [(a.target_time, a.generation_mw) for a in snapshot.actuals],
        )
        summary = snapshot.summary
        window = snapshot.window
        con.execute(
            "INSERT INTO ingestion_metadata VALUES (" + ", ".join(["?"] * 16) + ")",
            [
                snapshot.ingested_at.astimezone(UTC).replace(tzinfo=None),
                window.windfor_publish_from,
                window.windfor_publish_to,
                window.fuelhh_settlement_from,
                window.fuelhh_settlement_to,
                window.delivery_day_first,
                window.delivery_day_last,
                summary.forecast_rows_received,
                summary.forecast_rows_malformed,
                summary.forecast_duplicates_removed,
                summary.excluded_forecasts,
                summary.forecast_gap_hours,
                summary.actual_rows_received,
                summary.actual_rows_malformed,
                summary.actual_duplicates_removed,
                summary.actual_gap_periods,
            ],
        )
    finally:
        con.close()

    temp.chmod(SNAPSHOT_FILE_MODE)
    os.replace(temp, path)
