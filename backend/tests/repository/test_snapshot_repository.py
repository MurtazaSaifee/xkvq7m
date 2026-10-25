import shutil
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.repository.snapshot import SnapshotRepository, SnapshotUnavailableError


def test_reports_coverage_from_the_snapshot(snapshot_file: Path):
    coverage = SnapshotRepository(snapshot_file).coverage()

    assert coverage.ingested_at == datetime(2026, 10, 25, 10, 0, tzinfo=UTC)
    assert coverage.forecasts.first_target_time == datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    assert coverage.forecasts.last_target_time == datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    assert coverage.forecasts.row_count == 3
    assert coverage.actuals.first_target_time == datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    assert coverage.actuals.last_target_time == datetime(2026, 1, 2, 0, 30, tzinfo=UTC)
    assert coverage.actuals.row_count == 2
    assert coverage.excluded_forecasts == 7
    assert coverage.delivery_day_first == date(2026, 1, 2)
    assert coverage.delivery_day_last == date(2026, 2, 1)


def test_reading_does_not_change_the_file(snapshot_file: Path):
    before = snapshot_file.read_bytes()

    SnapshotRepository(snapshot_file).coverage()

    assert snapshot_file.read_bytes() == before


def test_a_missing_snapshot_is_unavailable_and_is_not_created(tmp_path: Path):
    missing = tmp_path / "absent.duckdb"

    with pytest.raises(SnapshotUnavailableError):
        SnapshotRepository(missing).coverage()

    assert not missing.exists()


def test_the_snapshot_is_opened_read_only_with_temp_files_in_the_system_temp_dir(
    snapshot_file: Path, monkeypatch: pytest.MonkeyPatch
):
    # Vercel's bundle is read-only and only /tmp is writable: DuckDB must not spill beside the file.
    opened: dict[str, object] = {}
    real_connect = duckdb.connect

    def recording_connect(database: str, **kwargs: Any) -> duckdb.DuckDBPyConnection:
        opened.update(kwargs)
        return real_connect(database, **kwargs)

    monkeypatch.setattr(duckdb, "connect", recording_connect)

    SnapshotRepository(snapshot_file).coverage()

    assert opened["read_only"] is True
    assert opened["config"] == {
        "temp_directory": tempfile.gettempdir(),
        "home_directory": tempfile.gettempdir(),
    }


def test_reads_from_a_read_only_directory(tmp_path: Path, snapshot_file: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    bundled = bundle / "snapshot.duckdb"
    shutil.copy(snapshot_file, bundled)
    bundled.chmod(0o444)
    bundle.chmod(0o555)
    try:
        coverage = SnapshotRepository(bundled).coverage()
    finally:
        bundle.chmod(0o755)

    assert coverage.forecasts.row_count == 3


def test_a_file_without_ingestion_metadata_is_unavailable(tmp_path: Path):
    empty = tmp_path / "empty.duckdb"
    duckdb.connect(str(empty)).close()

    with pytest.raises(SnapshotUnavailableError):
        SnapshotRepository(empty).coverage()
