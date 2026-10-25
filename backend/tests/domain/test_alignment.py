from datetime import datetime

from app.domain.alignment import forecast_error, hourly_actual, top_of_hour_actual

HOUR_START = datetime(2026, 1, 2, 10, 0)


def test_hourly_actual_is_the_mean_of_the_two_half_hours_in_the_hour():
    half_hours = {
        datetime(2026, 1, 2, 10, 0): 14000,
        datetime(2026, 1, 2, 10, 30): 14201,
    }

    assert hourly_actual(HOUR_START, half_hours) == 14100.5


def test_hourly_actual_ignores_half_hours_outside_the_hour():
    half_hours = {
        datetime(2026, 1, 2, 9, 30): 1,
        datetime(2026, 1, 2, 10, 0): 14000,
        datetime(2026, 1, 2, 10, 30): 14200,
        datetime(2026, 1, 2, 11, 0): 1,
    }

    assert hourly_actual(HOUR_START, half_hours) == 14100


def test_hourly_actual_is_missing_when_either_half_hour_is_missing():
    only_first = {datetime(2026, 1, 2, 10, 0): 14000}
    only_second = {datetime(2026, 1, 2, 10, 30): 14200}

    assert hourly_actual(HOUR_START, only_first) is None
    assert hourly_actual(HOUR_START, only_second) is None


def test_forecast_error_is_forecast_minus_actual_so_over_forecast_is_positive():
    assert forecast_error(forecast_mw=19000, actual_mw=17500.5) == 1499.5


def test_forecast_error_is_negative_when_wind_under_delivers_against_the_forecast():
    assert forecast_error(forecast_mw=12000, actual_mw=12500) == -500


def test_forecast_error_is_missing_when_either_side_is_missing():
    assert forecast_error(forecast_mw=None, actual_mw=12500) is None
    assert forecast_error(forecast_mw=12000, actual_mw=None) is None


def test_top_of_hour_actual_is_the_half_hour_starting_on_the_hour_alone():
    half_hours = {
        datetime(2026, 1, 2, 10, 0): 14000,
        datetime(2026, 1, 2, 10, 30): 14201,
    }

    assert top_of_hour_actual(HOUR_START, half_hours) == 14000


def test_top_of_hour_actual_is_missing_when_only_the_half_hour_past_the_hour_exists():
    only_second = {datetime(2026, 1, 2, 10, 30): 14200}

    assert top_of_hour_actual(HOUR_START, only_second) is None
