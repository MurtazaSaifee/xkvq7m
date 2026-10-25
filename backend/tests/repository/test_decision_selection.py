"""Decision-forecast selection (the ASOF join) against the shared decision fixture snapshot.

The expected values are written by hand from the rule: the latest forecast whose publish time is at
or before the cutoff, which is 09:20 UK on the decision day (the day before delivery). The fixture
rows and the case each one exercises are in ``tests/conftest.py``.
"""

from datetime import date, datetime
from pathlib import Path

from app.domain.decision import DecisionForecast, HalfHourActual, delivery_day_hours
from app.repository.snapshot import SnapshotRepository

FIRST_DAY = date(2026, 1, 2)
LAST_DAY = date(2026, 2, 1)
CUTOFF_FIRST = datetime(2026, 1, 1, 9, 20)
CUTOFF_LAST = datetime(2026, 1, 31, 9, 20)


def _selected(repo: SnapshotRepository, day: date, cutoff: datetime) -> dict[datetime, float]:
    forecasts = repo.decision_forecasts(delivery_day_hours(day), cutoff)
    return {f.target_time: f.generation_mw for f in forecasts}


def test_the_latest_forecast_at_or_before_the_cutoff_is_selected(decision_snapshot: Path):
    selected = _selected(SnapshotRepository(decision_snapshot), FIRST_DAY, CUTOFF_FIRST)

    assert selected[datetime(2026, 1, 2, 0, 0)] == 10100


def test_a_forecast_published_exactly_at_the_cutoff_is_used(decision_snapshot: Path):
    selected = _selected(SnapshotRepository(decision_snapshot), FIRST_DAY, CUTOFF_FIRST)

    assert selected[datetime(2026, 1, 2, 3, 0)] == 12100


def test_a_forecast_published_one_minute_after_the_cutoff_is_not_used(decision_snapshot: Path):
    selected = _selected(SnapshotRepository(decision_snapshot), FIRST_DAY, CUTOFF_FIRST)

    assert datetime(2026, 1, 2, 4, 0) not in selected


def test_a_target_with_no_forecast_published_before_the_cutoff_has_no_decision_forecast(
    decision_snapshot: Path,
):
    selected = _selected(SnapshotRepository(decision_snapshot), FIRST_DAY, CUTOFF_FIRST)

    assert datetime(2026, 1, 2, 1, 0) not in selected


def test_when_several_runs_cover_a_target_the_latest_before_the_cutoff_wins(
    decision_snapshot: Path,
):
    selected = _selected(SnapshotRepository(decision_snapshot), FIRST_DAY, CUTOFF_FIRST)

    assert selected[datetime(2026, 1, 2, 2, 0)] == 11000


def test_the_selected_publish_time_is_the_run_the_forecast_came_from(decision_snapshot: Path):
    forecasts = SnapshotRepository(decision_snapshot).decision_forecasts(
        delivery_day_hours(FIRST_DAY), CUTOFF_FIRST
    )
    by_target = {f.target_time: f for f in forecasts}

    assert by_target[datetime(2026, 1, 2, 2, 0)] == DecisionForecast(
        target_time=datetime(2026, 1, 2, 2, 0),
        publish_time=datetime(2026, 1, 1, 7, 30),
        generation_mw=11000,
    )


def test_the_last_delivery_day_in_scope_uses_its_own_decision_day(decision_snapshot: Path):
    selected = _selected(SnapshotRepository(decision_snapshot), LAST_DAY, CUTOFF_LAST)

    assert selected == {datetime(2026, 2, 1, 0, 0): 15000}


def test_only_the_targets_asked_for_are_returned(decision_snapshot: Path):
    forecasts = SnapshotRepository(decision_snapshot).decision_forecasts(
        delivery_day_hours(FIRST_DAY), CUTOFF_FIRST
    )

    assert {f.target_time.date() for f in forecasts} == {FIRST_DAY}


def test_actuals_are_returned_for_the_requested_half_hours_only(decision_snapshot: Path):
    # The range is [start, end): the decision day's 23:30 and the next day's 00:00 are both out.
    actuals = SnapshotRepository(decision_snapshot).actuals_between(
        datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 3, 0, 0)
    )

    assert actuals == [
        HalfHourActual(datetime(2026, 1, 2, 0, 0), 14000),
        HalfHourActual(datetime(2026, 1, 2, 0, 30), 14200),
    ]


def test_the_delivery_days_come_from_the_ingestion_window(decision_snapshot: Path):
    assert SnapshotRepository(decision_snapshot).delivery_days() == (FIRST_DAY, LAST_DAY)


def test_each_target_is_selected_against_its_own_cutoff(decision_snapshot: Path):
    # 2 Jan 00:00 with the 1 Jan cutoff at 09:20 selects the 09:20 run (10100). With the cutoff at
    # 07:30 only the 07:30 run is in time (10000). 1 Feb 00:00 uses its own cutoff on 31 Jan.
    forecasts = SnapshotRepository(decision_snapshot).decision_forecasts_at(
        [
            (datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 9, 20)),
            (datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 7, 30)),
            (datetime(2026, 2, 1, 0, 0), datetime(2026, 1, 31, 9, 20)),
        ]
    )

    assert sorted((f.target_time, f.publish_time, f.generation_mw) for f in forecasts) == [
        (datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 7, 30), 10000),
        (datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 9, 20), 10100),
        (datetime(2026, 2, 1, 0, 0), datetime(2026, 1, 31, 7, 30), 15000),
    ]


def test_reading_decision_forecasts_does_not_change_the_file(decision_snapshot: Path):
    before = decision_snapshot.read_bytes()

    SnapshotRepository(decision_snapshot).decision_forecasts(
        delivery_day_hours(FIRST_DAY), CUTOFF_FIRST
    )

    assert decision_snapshot.read_bytes() == before
