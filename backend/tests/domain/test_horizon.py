from collections.abc import Sequence
from datetime import datetime

import numpy as np
import pytest

from app.domain.decision import DecisionForecast, HalfHourActual
from app.domain.horizon import (
    ForecastColumns,
    HorizonCurve,
    decision_horizon_range,
    error_by_horizon,
    horizon_buckets,
    hourly_actuals,
)


def _seconds(*values: int) -> np.ndarray:
    return np.array(values, dtype=np.int64)


def test_bucket_k_holds_horizons_in_the_interval_k_minus_1_to_k_hours():
    # Seconds for 0, 1 s, 0.5 h, 1 h, 1 h + 1 s, 1.5 h, 2 h, 2 h + 1 s, 66 h, 66 h + 1 s, 66.5 h.
    seconds = _seconds(0, 1, 1800, 3600, 3601, 5400, 7200, 7201, 237600, 237601, 239400)

    assert horizon_buckets(seconds).tolist() == [1, 1, 1, 1, 2, 2, 2, 3, 66, 67, 67]


def test_a_run_published_at_0925_for_a_1300_target_falls_in_bucket_one():
    # The 12:25 run covers a 13:00 target at 35 minutes, which is not a whole-half-hour horizon.
    assert horizon_buckets(_seconds(1800, 35 * 60)).tolist() == [1, 1]


def test_a_horizon_of_zero_is_counted_in_bucket_one_rather_than_dropped():
    assert horizon_buckets(_seconds(0)).tolist() == [1]


def test_a_forecast_published_after_its_target_time_is_rejected():
    with pytest.raises(ValueError, match="after its target time"):
        horizon_buckets(_seconds(-1))


def test_hourly_actuals_are_the_mean_of_each_hours_two_half_hours_and_nan_otherwise():
    actuals = [
        HalfHourActual(datetime(2026, 1, 2, 0, 0), 100),
        HalfHourActual(datetime(2026, 1, 2, 0, 30), 200),
        # 01:00 has only its first half-hour, so the hour has no actual.
        HalfHourActual(datetime(2026, 1, 2, 1, 0), 300),
    ]

    values = hourly_actuals(datetime(2026, 1, 2, 0), datetime(2026, 1, 2, 3), actuals)

    assert values[0] == pytest.approx(150)
    assert np.isnan(values[1])
    assert np.isnan(values[2])


def _columns(rows: Sequence[tuple[datetime, datetime, float]]) -> ForecastColumns:
    return ForecastColumns(
        target_time=np.array([target for target, _, _ in rows], dtype="datetime64[us]"),
        publish_time=np.array([publish for _, publish, _ in rows], dtype="datetime64[us]"),
        generation_mw=np.array([mw for _, _, mw in rows], dtype=np.float64),
    )


# Window: 2 Jan 00:00 to 03:00, so the hourly actuals are 00:00 = 100, 01:00 = 200, 02:00 missing.
WINDOW_START = datetime(2026, 1, 2, 0, 0)
WINDOW_END = datetime(2026, 1, 2, 3, 0)
WINDOW_ACTUALS = [
    HalfHourActual(datetime(2026, 1, 2, 0, 0), 100),
    HalfHourActual(datetime(2026, 1, 2, 0, 30), 100),
    HalfHourActual(datetime(2026, 1, 2, 1, 0), 200),
    HalfHourActual(datetime(2026, 1, 2, 1, 30), 200),
]
# Each row is (target, publish, forecast MW). The horizon and error are worked out by hand.
KNOWN_HORIZONS = [
    # 0.5 h, error +10: bucket 1.
    (datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 23, 30), 110),
    # 35 min, error -10: bucket 1.
    (datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 23, 25), 90),
    # Exactly 2 h, error +30: the upper edge of bucket 2.
    (datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 22, 0), 130),
    # Exactly 2 h, error +20: bucket 2.
    (datetime(2026, 1, 2, 1, 0), datetime(2026, 1, 1, 23, 0), 220),
    # 2.5 h, error -20: bucket 3.
    (datetime(2026, 1, 2, 1, 0), datetime(2026, 1, 1, 22, 30), 180),
    # Published at its own target time, error +5: joins bucket 1.
    (datetime(2026, 1, 2, 1, 0), datetime(2026, 1, 2, 1, 0), 205),
    # 3 h with no actual for 02:00, so it is excluded and counted.
    (datetime(2026, 1, 2, 2, 0), datetime(2026, 1, 1, 23, 0), 500),
    # 24 h, error 0: bucket 24.
    (datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 0, 0), 100),
]


def _curve(
    rows: Sequence[tuple[datetime, datetime, float]],
    decision: list[DecisionForecast] | None = None,
) -> HorizonCurve:
    return error_by_horizon(
        WINDOW_START,
        WINDOW_END,
        _columns(rows),
        WINDOW_ACTUALS,
        decision_forecasts=decision or [],
    )


def test_each_bucket_reports_mae_bias_and_sample_count_for_its_known_horizons():
    curve = _curve(KNOWN_HORIZONS)

    first, second, third = curve.buckets[0], curve.buckets[1], curve.buckets[2]
    # Bucket 1: errors 10, -10 and 5.
    assert (first.lower_hours, first.upper_hours, first.sample_count) == (0, 1, 3)
    assert first.mae_mw == pytest.approx(25 / 3)
    assert first.bias_mw == pytest.approx(5 / 3)
    # Bucket 2: errors 30 and 20.
    assert (second.lower_hours, second.upper_hours, second.sample_count) == (1, 2, 2)
    assert second.mae_mw == pytest.approx(25)
    assert second.bias_mw == pytest.approx(25)
    # Bucket 3: error -20.
    assert (third.lower_hours, third.upper_hours, third.sample_count) == (2, 3, 1)
    assert third.mae_mw == pytest.approx(20)
    assert third.bias_mw == pytest.approx(-20)


def test_the_curve_runs_to_the_longest_horizon_and_empty_buckets_have_no_metrics():
    curve = _curve(KNOWN_HORIZONS)

    assert [b.upper_hours for b in curve.buckets] == list(range(1, 25))
    empty = curve.buckets[3]
    assert (empty.sample_count, empty.mae_mw, empty.bias_mw) == (0, None, None)
    last = curve.buckets[23]
    assert (last.sample_count, last.mae_mw, last.bias_mw) == (1, 0, 0)


def test_a_forecast_with_no_actual_is_left_out_and_counted_once():
    curve = _curve(KNOWN_HORIZONS)

    assert curve.excluded_no_actual == 1
    assert sum(b.sample_count for b in curve.buckets) == len(KNOWN_HORIZONS) - 1


def test_the_decision_horizon_range_is_the_shortest_and_longest_decision_horizon():
    decision = [
        DecisionForecast(datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 7, 30), 1),
        DecisionForecast(datetime(2026, 1, 2, 23, 0), datetime(2026, 1, 1, 7, 30), 1),
    ]

    curve = _curve(KNOWN_HORIZONS, decision)

    assert curve.decision_range is not None
    assert curve.decision_range.min_hours == pytest.approx(16.5)
    assert curve.decision_range.max_hours == pytest.approx(39.5)


def test_there_is_no_decision_range_without_decision_forecasts():
    assert _curve(KNOWN_HORIZONS).decision_range is None
    assert decision_horizon_range([]) is None


def test_no_forecast_in_the_window_gives_an_empty_curve():
    curve = _curve([])

    assert curve.buckets == []
    assert curve.excluded_no_actual == 0


def test_a_forecast_outside_the_window_is_rejected_rather_than_misindexed():
    with pytest.raises(ValueError, match="inside the window"):
        _curve([(datetime(2026, 1, 2, 5, 0), datetime(2026, 1, 1, 7, 30), 100)])
