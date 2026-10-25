from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.ingestion.build import SnapshotData, build_snapshot
from app.ingestion.store import write_snapshot
from app.ingestion.window import DEFAULT_WINDOW

INGESTED_AT = datetime(2026, 10, 25, 10, 0, tzinfo=UTC)


def windfor(publish: str, target: str, generation: int) -> dict[str, object]:
    return {
        "dataset": "WINDFOR",
        "publishTime": publish,
        "startTime": target,
        "generation": generation,
    }


def fuelhh(target: str, generation: int) -> dict[str, object]:
    return {
        "dataset": "FUELHH",
        "publishTime": target,
        "startTime": target,
        "generation": generation,
    }


@pytest.fixture
def snapshot_data() -> SnapshotData:
    windfor_rows = [
        windfor("2026-01-01T07:30:00Z", "2026-01-01T08:00:00Z", 19378),
        windfor("2026-01-01T07:30:00Z", "2026-01-01T09:00:00Z", 19400),
        windfor("2026-01-01T07:30:00Z", "2026-01-01T06:00:00Z", 19000),  # excluded: published late
        windfor("2026-01-01T07:30:00Z", "2026-01-01T08:00:00Z", 19378),  # duplicate
    ]
    fuelhh_rows = [fuelhh("2026-01-01T08:00:00Z", 15000), fuelhh("2026-01-01T08:30:00Z", 15100)]
    return build_snapshot(windfor_rows, fuelhh_rows, DEFAULT_WINDOW, INGESTED_AT)


def read_all(path: Path) -> dict[str, Any]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        return {
            "forecasts": con.execute(
                "SELECT publish_time, target_time, generation_mw FROM forecasts ORDER BY 1, 2"
            ).fetchall(),
            "actuals": con.execute(
                "SELECT target_time, generation_mw FROM actuals ORDER BY 1"
            ).fetchall(),
            "metadata": con.execute("SELECT * FROM ingestion_metadata").fetchall(),
        }
    finally:
        con.close()


def test_writes_clean_rows_and_a_metadata_row(tmp_path: Path, snapshot_data: SnapshotData):
    target = tmp_path / "snapshot.duckdb"

    write_snapshot(snapshot_data, target)

    contents = read_all(target)
    assert contents["forecasts"] == [
        (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 1, 8, 0), 19378),
        (datetime(2026, 1, 1, 7, 30), datetime(2026, 1, 1, 9, 0), 19400),
    ]
    assert contents["actuals"] == [
        (datetime(2026, 1, 1, 8, 0), 15000),
        (datetime(2026, 1, 1, 8, 30), 15100),
    ]
    (metadata,) = contents["metadata"]
    assert metadata[0] == datetime(2026, 10, 25, 10, 0)  # ingested_at, stored as naive UTC
    assert metadata[1:3] == (datetime(2025, 12, 18, 0, 0), datetime(2026, 2, 1, 23, 59))
    assert metadata[3:7] == (
        date(2025, 12, 19),
        date(2026, 2, 1),
        date(2026, 1, 2),
        date(2026, 2, 1),
    )
    # 19 Dec to 1 Feb inclusive: 45 days x 48 half-hours = 2160 expected, minus 2 present.
    assert metadata[7:] == (4, 0, 1, 1, 0, 2, 0, 0, 2158)


def test_replaces_an_existing_snapshot_and_leaves_no_temp_file(
    tmp_path: Path, snapshot_data: SnapshotData
):
    target = tmp_path / "snapshot.duckdb"
    target.write_bytes(b"stale")

    write_snapshot(snapshot_data, target)

    assert len(read_all(target)["forecasts"]) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["snapshot.duckdb"]


def test_running_twice_gives_the_same_data(tmp_path: Path, snapshot_data: SnapshotData):
    first = tmp_path / "first.duckdb"
    second = tmp_path / "second.duckdb"

    write_snapshot(snapshot_data, first)
    write_snapshot(snapshot_data, second)

    before = read_all(first)
    after = read_all(second)
    assert before["forecasts"] == after["forecasts"]
    assert before["actuals"] == after["actuals"]
    assert before["metadata"] == after["metadata"]
