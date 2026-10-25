from app.domain.kpis import day_kpis


def test_kpis_sum_hourly_mw_into_mwh_over_the_paired_hours():
    # Each hour is one hour long, so the sum of hourly MW is the energy in MWh.
    kpis = day_kpis(
        forecast_mw=[19000, 20000, 18000],
        actual_mw=[18000.5, 20500, 17000],
    )

    assert kpis.forecast_mwh == 57000
    assert kpis.actual_mwh == 55500.5
    assert kpis.paired_hours == 3


def test_error_mwh_is_forecast_minus_actual_and_equals_the_sum_of_hourly_errors():
    kpis = day_kpis(forecast_mw=[19000, 20000], actual_mw=[18000.5, 20500])

    assert kpis.error_mwh == 499.5
    assert kpis.error_mwh == (19000 - 18000.5) + (20000 - 20500)


def test_hours_missing_either_side_are_left_out_and_counted():
    kpis = day_kpis(
        forecast_mw=[19000, 20000, None, 18000],
        actual_mw=[18000, 20000, 15000, None],
    )

    assert kpis.paired_hours == 2
    assert kpis.forecast_mwh == 39000
    assert kpis.actual_mwh == 38000
    assert kpis.error_mwh == 1000
    assert kpis.missing_forecast_hours == 1
    assert kpis.missing_actual_hours == 1


def test_kpis_are_missing_when_no_hour_can_be_paired():
    kpis = day_kpis(forecast_mw=[None, None], actual_mw=[15000, None])

    assert kpis.paired_hours == 0
    assert kpis.forecast_mwh is None
    assert kpis.actual_mwh is None
    assert kpis.error_mwh is None
    assert kpis.missing_forecast_hours == 2
    assert kpis.missing_actual_hours == 1
