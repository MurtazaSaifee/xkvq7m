from pathlib import Path

import pytest

from app.core.config import SNAPSHOT_PATH_ENV, snapshot_path
from app.ingestion import __main__ as cli


@pytest.fixture
def written(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Replace the ingestion run with a recorder of the output paths it was given."""
    calls: list[Path] = []

    def record(output: Path) -> None:
        calls.append(output)

    monkeypatch.setattr(cli, "run_ingestion", record)
    return calls


def test_writes_to_the_configured_snapshot_path_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, written: list[Path]
):
    target = tmp_path / "configured.duckdb"
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(target))

    cli.main([])

    assert written == [target]
    assert snapshot_path() == target


def test_output_flag_overrides_the_configured_path(tmp_path: Path, written: list[Path]):
    cli.main(["--output", str(tmp_path / "other.duckdb")])

    assert written == [tmp_path / "other.duckdb"]
