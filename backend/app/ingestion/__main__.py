"""Command line entry point: ``python -m app.ingestion`` (run by ``make ingest``)."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from app.core.config import snapshot_path
from app.core.logging import configure_logging
from app.ingestion.run import run_ingestion


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.ingestion",
        description="Fetch the Elexon window and rebuild the DuckDB snapshot.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Snapshot file to write. Defaults to $WIND_SNAPSHOT_PATH, else data/snapshot.duckdb.",
    )
    args = parser.parse_args(argv)

    configure_logging()
    output: Path = args.output if args.output is not None else snapshot_path()
    run_ingestion(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
