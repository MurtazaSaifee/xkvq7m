import pytest

from app.core.config import REPO_ROOT, SNAPSHOT_PATH_ENV, snapshot_path


def test_snapshot_path_defaults_to_the_repo_data_dir(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(SNAPSHOT_PATH_ENV, raising=False)

    assert snapshot_path() == REPO_ROOT / "data" / "snapshot.duckdb"
    assert (REPO_ROOT / "backend" / "pyproject.toml").is_file()


def test_snapshot_path_can_be_overridden_by_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, "/somewhere/else/snap.duckdb")

    assert str(snapshot_path()) == "/somewhere/else/snap.duckdb"
