"""Every forecast in a window, as columns, against the shared decision fixture snapshot.

Rows for the window are counted by hand from ``DECISION_FORECASTS`` and ``CUTOFF_FORECASTS`` in
``tests/conftest.py``: for 2 Jan 00:00 to 06:00 the targets are 00:00 (3 runs), 01:00, 02:00 (2),
03:00 (2), 04:00 and 05:00, which is 10 rows. The start is inclusive and the end is exclusive.
"""

from datetime import datetime
from pathlib import Path

import numpy as np

from app.repository.snapshot import SnapshotRepository


def test_every_forecast_for_a_target_in_the_window_is_returned_not_only_the_latest(
    decision_snapshot: Path,
):
    columns = SnapshotRepository(decision_snapshot).forecasts_between(
        datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 2, 6, 0)
    )

    assert columns.target_time.size == 10
    assert np.sum(columns.target_time == np.datetime64("2026-01-02T00:00")) == 3


def test_the_end_of_the_window_is_exclusive_and_the_start_is_inclusive(decision_snapshot: Path):
    repo = SnapshotRepository(decision_snapshot)

    last_hour = repo.forecasts_between(datetime(2026, 1, 2, 5, 0), datetime(2026, 1, 2, 6, 0))
    no_targets_at_end = repo.forecasts_between(
        datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 2, 0, 0)
    )

    assert last_hour.target_time.tolist() == [np.datetime64("2026-01-02T05:00")]
    assert no_targets_at_end.target_time.size == 0


def test_the_columns_keep_publish_time_and_generation_with_their_dtypes(decision_snapshot: Path):
    columns = SnapshotRepository(decision_snapshot).forecasts_between(
        datetime(2026, 1, 2, 5, 0), datetime(2026, 1, 2, 6, 0)
    )

    assert columns.target_time.dtype == np.dtype("datetime64[us]")
    assert columns.publish_time.tolist() == [np.datetime64("2026-01-01T07:30:00")]
    assert columns.generation_mw.dtype == np.float64
    assert columns.generation_mw.tolist() == [13500.0]
