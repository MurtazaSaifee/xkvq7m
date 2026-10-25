"""Runtime configuration read from the environment, with defaults that work from a checkout."""

import os
from pathlib import Path

# backend/app/core/config.py -> repo root is three levels above the package directory.
REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_PATH_ENV = "WIND_SNAPSHOT_PATH"


def snapshot_path() -> Path:
    """Path of the DuckDB snapshot: ``$WIND_SNAPSHOT_PATH``, else ``data/snapshot.duckdb``."""
    configured = os.environ.get(SNAPSHOT_PATH_ENV)
    if configured:
        return Path(configured)
    return REPO_ROOT / "data" / "snapshot.duckdb"
