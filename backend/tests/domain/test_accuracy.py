from datetime import date, datetime, time

import pytest

from app.domain.accuracy import (
    ERROR_BIN_WIDTH_MW,
    accuracy_days,
    build_accuracy_report,
    decision_targets,
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


def test_accuracy_days_are_the_delivery_days_from_2_jan_to_1_feb_2026():
    days = accuracy_days()

    assert days[0] == date(2026, 1, 2)
    assert days[-1] == date(2026, 2, 1)
    assert len(days) == 31


def test_every_target_hour_is_paired_with_the_cutoff_of_its_own_delivery_day():
    targets = decision_targets(time(9, 20))

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

    report = build_accuracy_report(time(9, 20), forecasts, actuals)

    assert report.cutoff == time(9, 20)
    assert report.summary.target_hours == 31 * 24
    assert report.summary.measured_hours == 1
    assert report.summary.excluded_no_decision_forecast == 31 * 24 - 1
    assert report.summary.excluded_no_actual == 0
    assert report.summary.mae_mw == pytest.approx(900)  # 19000 - mean(18000, 18200) = 900
    assert report.summary.bias_mw == pytest.approx(900)
    assert sum(b.count for b in report.histogram) == 1
