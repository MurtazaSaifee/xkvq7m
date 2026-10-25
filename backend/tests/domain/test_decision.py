from datetime import date, datetime, time

from app.domain.decision import (
    DecisionForecast,
    HalfHourActual,
    build_decision_snapshot,
    delivery_day_half_hours,
    delivery_day_hours,
)

DAY = date(2026, 1, 2)
CUTOFF = time(9, 20)


def _forecast(target: datetime, publish: datetime, mw: float) -> DecisionForecast:
    return DecisionForecast(target_time=target, publish_time=publish, generation_mw=mw)


def test_a_january_delivery_day_has_24_hours_and_48_half_hours_in_utc():
    hours = delivery_day_hours(DAY)
    half_hours = delivery_day_half_hours(DAY)

    assert len(hours) == 24
    assert hours[0] == datetime(2026, 1, 2, 0, 0)
    assert hours[-1] == datetime(2026, 1, 2, 23, 0)
    assert len(half_hours) == 48
    assert half_hours[1] == datetime(2026, 1, 2, 0, 30)


def test_the_spring_clock_change_day_has_23_hours_and_ends_at_2300_utc():
    # Midnight is still GMT on 29 Mar 2026; the clocks go forward at 01:00 that morning.
    hours = delivery_day_hours(date(2026, 3, 29))

    assert len(hours) == 23
    assert hours[0] == datetime(2026, 3, 29, 0, 0)
    assert hours[-1] == datetime(2026, 3, 29, 22, 0)


def test_the_autumn_clock_change_day_has_25_hours():
    assert len(delivery_day_hours(date(2026, 10, 25))) == 25


def test_each_hour_takes_the_decision_forecast_and_the_aligned_actual():
    publish = datetime(2026, 1, 1, 7, 30)
    forecasts = [_forecast(datetime(2026, 1, 2, 10, 0), publish, 19000)]
    actuals = [
        HalfHourActual(datetime(2026, 1, 2, 10, 0), 18000),
        HalfHourActual(datetime(2026, 1, 2, 10, 30), 18200),
    ]

    snapshot = build_decision_snapshot(DAY, CUTOFF, forecasts, actuals)

    ten = snapshot.hours[10]
    assert ten.hour_start == datetime(2026, 1, 2, 10, 0)
    assert ten.publish_time == publish
    assert ten.forecast_mw == 19000
    assert ten.actual_mw == 18100
    assert ten.error_mw == 900


def test_an_hour_without_a_decision_forecast_is_a_gap_not_an_error():
    snapshot = build_decision_snapshot(DAY, CUTOFF, [], [])

    assert snapshot.hours[0].publish_time is None
    assert snapshot.hours[0].forecast_mw is None
    assert snapshot.hours[0].error_mw is None


def test_forecasts_published_after_the_cutoff_are_not_used():
    late = _forecast(datetime(2026, 1, 2, 10, 0), datetime(2026, 1, 1, 9, 30), 99999)

    snapshot = build_decision_snapshot(DAY, CUTOFF, [late], [])

    assert snapshot.hours[10].forecast_mw is None


def test_when_a_target_has_several_candidates_the_latest_one_at_or_before_the_cutoff_wins():
    earlier = _forecast(datetime(2026, 1, 2, 10, 0), datetime(2026, 1, 1, 5, 30), 1000)
    latest = _forecast(datetime(2026, 1, 2, 10, 0), datetime(2026, 1, 1, 7, 30), 2000)
    too_late = _forecast(datetime(2026, 1, 2, 10, 0), datetime(2026, 1, 1, 9, 30), 3000)

    snapshot = build_decision_snapshot(DAY, CUTOFF, [earlier, latest, too_late], [])

    assert snapshot.hours[10].forecast_mw == 2000
    assert snapshot.hours[10].publish_time == datetime(2026, 1, 1, 7, 30)


def test_the_forecast_run_used_is_the_latest_publish_time_among_the_selected_forecasts():
    forecasts = [
        _forecast(datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 1, 7, 30), 1),
        _forecast(datetime(2026, 1, 2, 1, 0), datetime(2026, 1, 1, 7, 30), 1),
    ]

    snapshot = build_decision_snapshot(DAY, CUTOFF, forecasts, [])

    assert snapshot.forecast_run_publish_time == datetime(2026, 1, 1, 7, 30)


def test_there_is_no_forecast_run_when_nothing_was_published_before_the_cutoff():
    snapshot = build_decision_snapshot(DAY, CUTOFF, [], [])

    assert snapshot.forecast_run_publish_time is None
    assert snapshot.kpis.paired_hours == 0


def test_the_snapshot_lists_all_half_hours_with_gaps_as_none():
    actuals = [HalfHourActual(datetime(2026, 1, 2, 0, 0), 14000)]

    snapshot = build_decision_snapshot(DAY, CUTOFF, [], actuals)

    assert len(snapshot.actuals) == 48
    assert snapshot.actuals[0].generation_mw == 14000
    assert snapshot.actuals[1].generation_mw is None


def test_the_cutoff_is_recorded_as_a_utc_instant_on_the_decision_day():
    snapshot = build_decision_snapshot(DAY, CUTOFF, [], [])

    assert snapshot.decision_day == date(2026, 1, 1)
    assert snapshot.cutoff_time == datetime(2026, 1, 1, 9, 20)
