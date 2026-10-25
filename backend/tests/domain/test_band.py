"""Expected-error band: the walk-forward P10 and P90 of past decision-forecast errors, and coverage.

Error is forecast minus actual, so the band for an actual is [forecast - P90, forecast - P10].
Expected values are hand-computed from small inputs. The hour grid and half-hours are written out
here, not taken from the code under test.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime, time, timedelta

import pytest

from app.domain.band import (
    BAND_LOOKBACK_DAYS,
    BAND_MIN_HISTORY_DAYS,
    ExpectedErrorBand,
    band_for_day,
    build_band_coverage,
    expected_error_band,
    lookback_days,
)
from app.domain.decision import DecisionForecast, HalfHourActual

CUTOFF = time(9, 20)
DAY = date(2026, 1, 2)
# The fourteen delivery days that end two days before 2 Jan: 18 Dec 2025 to 31 Dec.
LOOKBACK = [date(2025, 12, 18) + timedelta(days=offset) for offset in range(14)]
FORECAST_MW = 10000.0


def _inputs_with_hourly_actuals(
    day: date, forecast_mw: float, hourly_actual_mw: Sequence[float]
) -> tuple[list[DecisionForecast], list[HalfHourActual]]:
    """Decision forecasts for every hour of ``day``, published 07:30 on the day before, and each
    half-hour actual equal to its hour's value."""
    decided_at = datetime.combine(day - timedelta(days=1), time(7, 30))
    start = datetime.combine(day, time(0))
    forecasts = [
        DecisionForecast(start + timedelta(hours=hour), decided_at, forecast_mw)
        for hour in range(24)
    ]
    actuals = [
        HalfHourActual(start + timedelta(minutes=30 * half), hourly_actual_mw[half // 2])
        for half in range(48)
    ]
    return forecasts, actuals


def _inputs_with_error(
    day: date, error_mw: float
) -> tuple[list[DecisionForecast], list[HalfHourActual]]:
    """A day whose every hourly decision-forecast error is ``error_mw``."""
    return _inputs_with_hourly_actuals(day, FORECAST_MW, [FORECAST_MW - error_mw] * 24)


def _flatten(
    parts: Sequence[tuple[list[DecisionForecast], list[HalfHourActual]]],
) -> tuple[list[DecisionForecast], list[HalfHourActual]]:
    forecasts: list[DecisionForecast] = []
    actuals: list[HalfHourActual] = []
    for part_forecasts, part_actuals in parts:
        forecasts.extend(part_forecasts)
        actuals.extend(part_actuals)
    return forecasts, actuals


def _seven_past_days() -> dict[date, list[float]]:
    """One error per day, 0 to 600 MW in steps of 100, over the first seven December days."""
    return {day: [100.0 * index] for index, day in enumerate(LOOKBACK[:7])}


def test_the_band_for_an_actual_is_forecast_minus_p90_to_forecast_minus_p10():
    # Errors 0, 100, ..., 600. P10 sits at position 0.6 (60 MW) and P90 at 5.4 (540 MW).
    band = expected_error_band(DAY, _seven_past_days())

    assert band is not None
    assert (band.lower_error_mw, band.upper_error_mw) == pytest.approx((60, 540))
    assert band.actual_range_mw(10000) == pytest.approx((9460, 9940))


def test_the_band_reads_the_fourteen_delivery_days_that_end_two_days_before_the_day():
    assert BAND_LOOKBACK_DAYS == 14
    assert lookback_days(DAY) == LOOKBACK
    assert lookback_days(DAY)[-1] == DAY - timedelta(days=2)


def test_changing_the_day_before_the_day_itself_or_any_later_day_does_not_move_the_band():
    past = _seven_past_days()
    later = {DAY + timedelta(days=offset): [1_000_000.0] for offset in range(-1, 31)}

    assert expected_error_band(DAY, {**past, **later}) == expected_error_band(DAY, past)


def test_the_two_end_days_of_the_lookback_move_the_band_and_the_day_before_does_not():
    # 31 Dec is two days before 2 Jan, the newest day read. 18 Dec is the oldest.
    past = {LOOKBACK[7 + index]: [100.0 * index] for index in range(7)}
    last_changed = {**past, LOOKBACK[13]: [0.0]}
    first = _seven_past_days()
    first_changed = {**first, LOOKBACK[0]: [5000.0]}
    day_before_changed = {**past, DAY - timedelta(days=1): [5000.0]}

    assert expected_error_band(DAY, last_changed) != expected_error_band(DAY, past)
    assert expected_error_band(DAY, first_changed) != expected_error_band(DAY, first)
    assert expected_error_band(DAY, day_before_changed) == expected_error_band(DAY, past)


def test_errors_older_than_the_lookback_window_do_not_move_the_band():
    # 17 Dec is sixteen days before 2 Jan, just outside the window that starts on 18 Dec.
    older = {LOOKBACK[0] - timedelta(days=1): [9000.0]}

    assert expected_error_band(DAY, {**_seven_past_days(), **older}) == expected_error_band(
        DAY, _seven_past_days()
    )


def test_a_band_needs_at_least_seven_past_days_with_errors():
    assert BAND_MIN_HISTORY_DAYS == 7
    six = {day: [100.0 * index] for index, day in enumerate(LOOKBACK[:6])}

    assert expected_error_band(DAY, six) is None
    band = expected_error_band(DAY, _seven_past_days())
    assert band is not None
    assert band.history_days == 7


def test_past_days_without_measured_errors_do_not_count_towards_the_minimum():
    seven = _seven_past_days()
    seven[LOOKBACK[3]] = []  # a day with forecasts but no measured hour

    assert expected_error_band(DAY, seven) is None


def test_the_percentiles_pool_every_hourly_error_of_the_past_days():
    # Day k holds 24 errors of 100k MW. Pooled, the first 24 values are zero, so P10 is 0. The last
    # 24 are 600, so P90 is 600. A mean per day would give 60 and 540 instead.
    errors: Mapping[date, Sequence[float]] = {
        day: [100.0 * index] * 24 for index, day in enumerate(LOOKBACK[:7])
    }

    band = expected_error_band(DAY, errors)

    assert band is not None
    assert (band.lower_error_mw, band.upper_error_mw) == pytest.approx((0, 600))


def test_fewer_than_fourteen_past_days_use_the_days_available():
    # A snapshot that starts on 25 Dec has seven of the fourteen past days for 2 Jan.
    inputs = [_inputs_with_error(day, 100.0 * index) for index, day in enumerate(LOOKBACK[7:])]
    forecasts, actuals = _flatten(inputs)
    band = band_for_day(DAY, CUTOFF, forecasts, actuals)

    assert band is not None
    assert band.history_days == 7


def test_six_available_past_days_give_no_band_for_the_day():
    inputs = [_inputs_with_error(day, 100.0 * index) for index, day in enumerate(LOOKBACK[8:])]
    forecasts, actuals = _flatten(inputs)

    assert band_for_day(DAY, CUTOFF, forecasts, actuals) is None


def test_the_band_uses_only_forecasts_published_by_the_cutoff():
    # Each past day has a 07:30 run at 10000 and a 09:30 run at 11000 for the same hours. Actuals
    # are 9000. At 09:20 only the 07:30 run is in time (error 1000). At 09:30 the 09:30 run is also
    # in time, so the decision forecast is 11000 (error 2000).
    forecasts: list[DecisionForecast] = []
    actuals: list[HalfHourActual] = []
    for day in LOOKBACK[:7]:
        early_forecasts, early_actuals = _inputs_with_hourly_actuals(day, 10000.0, [9000.0] * 24)
        late_run = datetime.combine(day - timedelta(days=1), time(9, 30))
        late_forecasts = [
            DecisionForecast(hour.target_time, late_run, 11000.0) for hour in early_forecasts
        ]
        forecasts.extend([*early_forecasts, *late_forecasts])
        actuals.extend(early_actuals)

    at_0920 = band_for_day(DAY, time(9, 20), forecasts, actuals)
    at_0930 = band_for_day(DAY, time(9, 30), forecasts, actuals)

    assert at_0920 is not None and at_0930 is not None
    assert (at_0920.lower_error_mw, at_0920.upper_error_mw) == pytest.approx((1000, 1000))
    assert (at_0930.lower_error_mw, at_0930.upper_error_mw) == pytest.approx((2000, 2000))


@pytest.mark.parametrize("day_offset", [-1, 0, 1, 10])
@pytest.mark.parametrize("field", ["actual", "forecast"])
def test_changing_an_actual_or_forecast_on_the_day_before_or_later_does_not_move_the_band(
    field: str, day_offset: int
):
    target = DAY + timedelta(days=day_offset)
    past = _flatten(
        [_inputs_with_error(day, 100.0 * index) for index, day in enumerate(LOOKBACK[:7])]
    )
    recent = _flatten(
        [_inputs_with_error(DAY + timedelta(days=offset), 5000.0) for offset in (-1, 0, 1, 10)]
    )
    forecasts, actuals = _flatten([past, recent])
    band = band_for_day(DAY, CUTOFF, forecasts, actuals)
    assert band is not None

    if field == "forecast":
        forecasts = [
            replace(f, generation_mw=f.generation_mw + 7000.0)
            if f.target_time.date() == target
            else f
            for f in forecasts
        ]
    else:
        actuals = [
            replace(a, generation_mw=(a.generation_mw or 0.0) + 7000.0)
            if a.target_time.date() == target
            else a
            for a in actuals
        ]

    assert band_for_day(DAY, CUTOFF, forecasts, actuals) == band


def test_an_hour_with_no_decision_forecast_has_no_band_range():
    band = ExpectedErrorBand(lower_error_mw=60, upper_error_mw=540, history_days=7)

    assert band.actual_range_mw(None) == (None, None)


def test_band_coverage_counts_hours_inside_the_band_with_inclusive_edges():
    # Each past day holds 24 hourly errors of 100k MW. Pooled, the errors run 0 to 600, so P10 is 0
    # and P90 is 600. For forecast 10000 the band for 2 Jan is [9400, 10000].
    # Hour 0 sits on the lower edge and hour 1 on the upper edge: both inside. Hour 2 is just below
    # and hour 3 just above: both outside. The other twenty hours are inside.
    history = _flatten(
        [_inputs_with_error(day, 100.0 * index) for index, day in enumerate(LOOKBACK[:7])]
    )
    hourly = [9400.0, 10000.0, 9399.0, 10001.0] + [9700.0] * 20
    scope = _inputs_with_hourly_actuals(DAY, FORECAST_MW, hourly)

    coverage = build_band_coverage([DAY], CUTOFF, *_flatten([history, scope]))

    assert coverage.counted_hours == 24
    assert coverage.inside_hours == 22
    assert coverage.coverage_percent == pytest.approx(22 / 24 * 100)
    assert coverage.excluded_no_band == 0
    assert coverage.excluded_no_decision_forecast == 0
    assert coverage.excluded_no_actual == 0


def test_band_coverage_leaves_out_and_counts_hours_with_no_forecast_no_actual_or_no_band():
    history = _flatten(
        [_inputs_with_error(day, 100.0 * index) for index, day in enumerate(LOOKBACK[:7])]
    )
    forecasts, actuals = _inputs_with_hourly_actuals(DAY, FORECAST_MW, [9700.0] * 24)
    # Hour 0 loses its decision forecast. Hour 1 loses both of its half-hour actuals.
    forecasts = [f for f in forecasts if f.target_time != datetime(2026, 1, 2, 0, 0)]
    actuals = [
        a
        for a in actuals
        if a.target_time not in (datetime(2026, 1, 2, 1, 0), datetime(2026, 1, 2, 1, 30))
    ]

    coverage = build_band_coverage([DAY], CUTOFF, *_flatten([history, (forecasts, actuals)]))

    assert coverage.excluded_no_decision_forecast == 1
    assert coverage.excluded_no_actual == 1
    assert coverage.counted_hours == 22
    assert (
        coverage.counted_hours
        + coverage.excluded_no_decision_forecast
        + coverage.excluded_no_actual
        + coverage.excluded_no_band
        == 24
    )


def test_a_scope_day_with_no_band_has_no_coverage_and_every_hour_is_excluded_as_no_band():
    scope = _inputs_with_hourly_actuals(DAY, FORECAST_MW, [9700.0] * 24)

    coverage = build_band_coverage([DAY], CUTOFF, *scope)

    assert coverage.counted_hours == 0
    assert coverage.inside_hours == 0
    assert coverage.excluded_no_band == 24
    assert coverage.coverage_percent is None
