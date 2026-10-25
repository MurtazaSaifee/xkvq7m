from datetime import date, datetime, time

import pytest

from app.domain.accuracy import (
    ERROR_BIN_WIDTH_MW,
    accuracy_window,
    alignment_sensitivity,
    build_accuracy_report,
    decision_targets,
    delivery_days_between,
    error_histogram,
    summarise_accuracy,
)
from app.domain.decision import DecisionForecast, HalfHourActual


def test_metrics_match_hand_computed_values_for_four_hours():
    # Errors (forecast - actual) are 10, -10, 30 and 0. Actual is 100 in every hour.
    summary = summarise_accuracy(
        forecast_mw=[110, 90, 130, 100],
        actual_mw=[100, 100, 100, 100],
    )

    assert summary.measured_hours == 4
    assert summary.mae_mw == pytest.approx(12.5)  # (10 + 10 + 30 + 0) / 4
    assert summary.bias_mw == pytest.approx(7.5)  # (10 - 10 + 30 + 0) / 4
    assert summary.rmse_mw == pytest.approx(275**0.5)  # sqrt((100 + 100 + 900 + 0) / 4)
    assert summary.p90_abs_error_mw == pytest.approx(24.0)  # sorted |e| 0, 10, 10, 30; position 2.7
    assert summary.mean_actual_mw == pytest.approx(100)
    assert summary.nmae_percent == pytest.approx(12.5)  # 12.5 / 100 as a percentage


def test_p90_absolute_error_interpolates_between_the_ninth_and_tenth_values():
    # Absolute errors 1 to 10. The 90th percentile is at position 8.1 (0-based): a tenth of the
    # way from the 9th value to the 10th.
    forecast = [100 + k for k in range(1, 11)]
    actual = [100] * 10

    summary = summarise_accuracy(forecast_mw=forecast, actual_mw=actual)

    assert summary.p90_abs_error_mw == pytest.approx(9.1)


def test_bias_is_negative_when_wind_comes_in_above_the_forecast():
    summary = summarise_accuracy(forecast_mw=[90, 80], actual_mw=[100, 100])

    assert summary.bias_mw == pytest.approx(-15)
    assert summary.mae_mw == pytest.approx(15)


def test_hours_without_a_decision_forecast_or_an_actual_are_excluded_and_counted():
    # 6 hours have both. One has a forecast but no actual. Two have no decision forecast at all.
    forecast = [19000, 18000, 17000, 15000, 12000, 12500, 12000, None, None]
    actual = [18100, 18500, 17000, 14000, 12500, 12100, None, 1, 1]

    summary = summarise_accuracy(forecast_mw=forecast, actual_mw=actual)

    assert summary.target_hours == 9
    assert summary.measured_hours == 6
    assert summary.excluded_no_decision_forecast == 2
    assert summary.excluded_no_actual == 1
    assert (
        summary.measured_hours
        + summary.excluded_no_decision_forecast
        + (summary.excluded_no_actual)
        == summary.target_hours
    )


def test_metrics_are_missing_when_no_hour_can_be_measured():
    summary = summarise_accuracy(forecast_mw=[None, 100], actual_mw=[100, None])

    assert summary.measured_hours == 0
    assert summary.mae_mw is None
    assert summary.bias_mw is None
    assert summary.rmse_mw is None
    assert summary.p90_abs_error_mw is None
    assert summary.mean_actual_mw is None
    assert summary.nmae_percent is None


def test_nmae_is_missing_when_mean_actual_is_zero():
    # Mean actual is zero, so the percentage is undefined even though MAE is defined.
    summary = summarise_accuracy(forecast_mw=[5, -5], actual_mw=[0, 0])

    assert summary.mae_mw == pytest.approx(5)
    assert summary.mean_actual_mw == 0
    assert summary.nmae_percent is None


def test_error_bins_are_fixed_width_and_cover_every_error():
    # Errors -1200, -499.9, 0, 0, 499.9, 500, 1600 fall into 500 MW bins on multiples of 500.
    bins = error_histogram(
        forecast_mw=[-1200, -499.9, 0, 0, 499.9, 500, 1600],
        actual_mw=[0] * 7,
    )

    assert ERROR_BIN_WIDTH_MW == 500
    assert [(b.lower_mw, b.upper_mw) for b in bins] == [
        (-1500, -1000),
        (-1000, -500),
        (-500, 0),
        (0, 500),
        (500, 1000),
        (1000, 1500),
        (1500, 2000),
    ]
    assert [b.count for b in bins] == [1, 0, 1, 3, 1, 0, 1]
    assert sum(b.count for b in bins) == 7


def test_the_largest_error_lands_in_the_last_bin_which_is_closed_on_the_right():
    bins = error_histogram(forecast_mw=[1000, 0], actual_mw=[0, 0])

    assert bins[-1].upper_mw == 1000
    assert bins[-1].count == 1


def test_a_zero_error_gets_a_bin_even_when_all_errors_are_zero():
    bins = error_histogram(forecast_mw=[100, 100], actual_mw=[100, 100])

    assert [(b.lower_mw, b.upper_mw, b.count) for b in bins] == [(0, 500, 2)]


def test_no_measured_hours_gives_no_histogram_bins():
    assert error_histogram(forecast_mw=[None], actual_mw=[None]) == []


JANUARY_DAYS = delivery_days_between(date(2026, 1, 2), date(2026, 2, 1))


def test_delivery_days_run_from_first_to_last_inclusive():
    days = delivery_days_between(date(2026, 1, 2), date(2026, 2, 1))

    assert days[0] == date(2026, 1, 2)
    assert days[-1] == date(2026, 2, 1)
    assert len(days) == 31


def test_the_domain_is_not_pinned_to_january_so_the_december_warm_up_days_work_too():
    # The walk-forward band needs 19 Dec to 1 Jan. The same rules must apply to those days.
    warm_up = delivery_days_between(date(2025, 12, 19), date(2026, 1, 1))
    targets = decision_targets(warm_up, time(9, 20))

    assert len(warm_up) == 14
    assert len(targets) == 14 * 24
    # 19 Dec is decided on 18 Dec at 09:20 UK time, which is 09:20 UTC in December too.
    assert targets[0] == (datetime(2025, 12, 19, 0, 0), datetime(2025, 12, 18, 9, 20))


def test_the_window_of_actuals_spans_the_first_day_to_the_end_of_the_last():
    start, end = accuracy_window(JANUARY_DAYS)

    assert start == datetime(2026, 1, 2, 0, 0)
    assert end == datetime(2026, 2, 2, 0, 0)


def test_every_target_hour_is_paired_with_the_cutoff_of_its_own_delivery_day():
    targets = decision_targets(JANUARY_DAYS, time(9, 20))

    assert len(targets) == 31 * 24
    # 2 Jan 00:00 is decided at 09:20 UK time on 1 Jan, which is 09:20 UTC in January.
    assert targets[0] == (datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 9, 20))
    assert targets[-1] == (datetime(2026, 2, 1, 23, 0), datetime(2026, 1, 31, 9, 20))


def test_the_report_selects_and_aligns_like_a_decision_snapshot_and_counts_exclusions():
    # Only 2 Jan 00:00 has a decision forecast (published 07:30 on 1 Jan) and a full actual.
    # A forecast for 01:00 published after the 09:20 cutoff is not used, so 01:00 is excluded.
    forecasts = [
        DecisionForecast(datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 7, 30), 19000),
        DecisionForecast(datetime(2026, 1, 2, 1, 0), datetime(2026, 1, 1, 9, 30), 99999),
        # Outside the scope, so it is ignored rather than counted as a target hour.
        DecisionForecast(datetime(2026, 1, 1, 0, 0), datetime(2025, 12, 31, 7, 30), 1),
    ]
    actuals = [
        HalfHourActual(datetime(2026, 1, 2, 0, 0), 18000),
        HalfHourActual(datetime(2026, 1, 2, 0, 30), 18200),
    ]

    report = build_accuracy_report(JANUARY_DAYS, time(9, 20), forecasts, actuals)

    assert report.cutoff == time(9, 20)
    assert (report.first_day, report.last_day) == (date(2026, 1, 2), date(2026, 2, 1))
    assert report.summary.target_hours == 31 * 24
    assert report.summary.measured_hours == 1
    assert report.summary.excluded_no_decision_forecast == 31 * 24 - 1
    assert report.summary.excluded_no_actual == 0
    assert report.summary.mae_mw == pytest.approx(900)  # 19000 - mean(18000, 18200) = 900
    assert report.summary.bias_mw == pytest.approx(900)
    assert sum(b.count for b in report.histogram) == 1


def test_alignment_sensitivity_compares_the_hourly_mean_with_the_top_of_hour_actual():
    # One delivery day, with decision forecasts at 09:20 for four hours and nothing else.
    # 00:00: halves 18000 and 18200, mean 18100, top 18000. Forecast 19000: errors 900 and 1000.
    # 01:00: halves 18500 and 18500, so both rules give 18500. Forecast 18000: error -500 both ways.
    # 02:00: only the 02:00 half-hour exists. Forecast 17000: measured at the top of the hour only.
    # 03:00: only the 03:30 half-hour exists. Forecast 17000: measured under neither rule.
    forecasts = [
        DecisionForecast(datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 7, 30), 19000),
        DecisionForecast(datetime(2026, 1, 2, 1, 0), datetime(2026, 1, 1, 7, 30), 18000),
        DecisionForecast(datetime(2026, 1, 2, 2, 0), datetime(2026, 1, 1, 7, 30), 17000),
        DecisionForecast(datetime(2026, 1, 2, 3, 0), datetime(2026, 1, 1, 7, 30), 17000),
    ]
    actuals = [
        HalfHourActual(datetime(2026, 1, 2, 0, 0), 18000),
        HalfHourActual(datetime(2026, 1, 2, 0, 30), 18200),
        HalfHourActual(datetime(2026, 1, 2, 1, 0), 18500),
        HalfHourActual(datetime(2026, 1, 2, 1, 30), 18500),
        HalfHourActual(datetime(2026, 1, 2, 2, 0), 16000),
        HalfHourActual(datetime(2026, 1, 2, 3, 30), 15000),
    ]

    result = alignment_sensitivity([date(2026, 1, 2)], time(9, 20), forecasts, actuals)

    # Hourly mean measures 00:00 and 01:00: errors 900 and -500.
    assert result.hourly_mean.measured_hours == 2
    assert result.hourly_mean.mae_mw == pytest.approx(700)
    assert result.hourly_mean.bias_mw == pytest.approx(200)
    assert result.hourly_mean.rmse_mw == pytest.approx(530000**0.5)
    assert result.hourly_mean.excluded_no_decision_forecast == 20
    assert result.hourly_mean.excluded_no_actual == 2
    # Top of hour measures 00:00, 01:00 and 02:00: errors 1000, -500 and 1000.
    assert result.top_of_hour.measured_hours == 3
    assert result.top_of_hour.mae_mw == pytest.approx(2500 / 3)
    assert result.top_of_hour.bias_mw == pytest.approx(500)
    assert result.top_of_hour.rmse_mw == pytest.approx(750000**0.5)
    assert result.top_of_hour.excluded_no_decision_forecast == 20
    assert result.top_of_hour.excluded_no_actual == 1


def test_the_hourly_mean_side_of_the_sensitivity_is_the_headline_summary():
    forecasts = [
        DecisionForecast(datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 7, 30), 19000),
        DecisionForecast(datetime(2026, 1, 2, 1, 0), datetime(2026, 1, 1, 7, 30), 18000),
    ]
    actuals = [
        HalfHourActual(datetime(2026, 1, 2, 0, 0), 18000),
        HalfHourActual(datetime(2026, 1, 2, 0, 30), 18200),
        HalfHourActual(datetime(2026, 1, 2, 1, 0), 18500),
        HalfHourActual(datetime(2026, 1, 2, 1, 30), 18500),
    ]
    days = [date(2026, 1, 2)]

    report = build_accuracy_report(days, time(9, 20), forecasts, actuals)
    result = alignment_sensitivity(days, time(9, 20), forecasts, actuals)

    assert result.hourly_mean == report.summary
