from datetime import date, datetime, time, timedelta

from app.domain.decision import DecisionForecast, HalfHourActual
from app.domain.error_grid import build_error_grid

CUTOFF = time(9, 20)


def _forecasts(day: date, hourly_mw: dict[int, float], publish: datetime) -> list[DecisionForecast]:
    """Hourly forecasts for ``day``, keyed by the hour (0-23, UTC) the target starts at."""
    base = datetime.combine(day, time(0))
    return [
        DecisionForecast(
            target_time=base + timedelta(hours=hour), publish_time=publish, generation_mw=mw
        )
        for hour, mw in hourly_mw.items()
    ]


def _actuals(day: date, hourly_mw: dict[int, float]) -> list[HalfHourActual]:
    """Both half-hours of each hour carry the same MW, so the hourly actual is that MW."""
    base = datetime.combine(day, time(0))
    actuals: list[HalfHourActual] = []
    for hour, mw in hourly_mw.items():
        start = base + timedelta(hours=hour)
        actuals.append(HalfHourActual(target_time=start, generation_mw=mw))
        actuals.append(HalfHourActual(target_time=start + timedelta(minutes=30), generation_mw=mw))
    return actuals


def _flat_day(
    day: date, actual_mw: float, error_mw: float
) -> tuple[list[DecisionForecast], list[HalfHourActual]]:
    """A day where the decision forecast is ``error_mw`` above the actual in every hour.

    The forecasts are published at 07:30 on the decision day, before the 09:20 cutoff.
    """
    publish = datetime.combine(day - timedelta(days=1), time(7, 30))
    hours = range(24)
    return (
        _forecasts(day, {hour: actual_mw + error_mw for hour in hours}, publish),
        _actuals(day, {hour: actual_mw for hour in hours}),
    )


def _scope(
    days_and_errors: dict[date, float],
) -> tuple[list[DecisionForecast], list[HalfHourActual]]:
    forecasts: list[DecisionForecast] = []
    actuals: list[HalfHourActual] = []
    for day, error_mw in days_and_errors.items():
        day_forecasts, day_actuals = _flat_day(day, actual_mw=10000, error_mw=error_mw)
        forecasts += day_forecasts
        actuals += day_actuals
    return forecasts, actuals


def test_each_cell_holds_the_decision_forecast_error_for_its_delivery_day_and_uk_hour():
    # Delivery day 2 Jan, decision day 1 Jan. Forecasts are published at 07:30 on 1 Jan, before the
    # 09:20 cutoff. The 01:00 hour has an actual but no forecast; the 02:00 hour is over-forecast.
    day = date(2026, 1, 2)
    publish = datetime(2026, 1, 1, 7, 30)
    forecasts = _forecasts(day, {0: 19000, 2: 17000}, publish)
    actuals = _actuals(day, {0: 18000, 1: 18500, 2: 16000})

    grid = build_error_grid([day], CUTOFF, forecasts, actuals)

    cells = {(c.delivery_day, c.hour): c.error_mw for c in grid.heatmap}
    assert len(grid.heatmap) == 24
    assert cells[(day, 0)] == 1000  # 19,000 - 18,000
    assert cells[(day, 1)] is None  # no decision forecast for 01:00
    assert cells[(day, 2)] == 1000  # 17,000 - 16,000
    assert cells[(day, 3)] is None  # neither a forecast nor an actual


def test_worst_days_rank_by_absolute_daily_energy_error_and_keep_the_sign():
    # Each hour is one hour long, so a day's energy error is the sum of its hourly errors:
    # 2 Jan is +100 MW for 24 hours (+2,400 MWh), 3 Jan is -300 MW (-7,200 MWh), 4 Jan is +50 MW.
    forecasts, actuals = _scope({date(2026, 1, 2): 100, date(2026, 1, 3): -300, date(2026, 1, 4): 50})
    days = [date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)]

    grid = build_error_grid(days, CUTOFF, forecasts, actuals, worst_count=2)

    assert [(w.delivery_day, w.error_mwh) for w in grid.worst_days] == [
        (date(2026, 1, 3), -7200),
        (date(2026, 1, 2), 2400),
    ]
    worst = grid.worst_days[0]
    assert worst.forecast_mwh == 10000 * 24 - 300 * 24
    assert worst.actual_mwh == 10000 * 24
    assert worst.paired_hours == 24


def test_a_day_with_no_measured_hour_is_not_ranked():
    # 5 Jan has decision forecasts but no actuals, so it has no energy error to rank.
    days = [date(2026, 1, 2), date(2026, 1, 5)]
    forecasts, actuals = _scope({date(2026, 1, 2): 100})
    publish = datetime(2026, 1, 4, 7, 30)
    forecasts += _forecasts(date(2026, 1, 5), {hour: 9000 for hour in range(24)}, publish)

    grid = build_error_grid(days, CUTOFF, forecasts, actuals)

    assert [w.delivery_day for w in grid.worst_days] == [date(2026, 1, 2)]


def test_equal_absolute_errors_are_ordered_by_the_earlier_day():
    forecasts, actuals = _scope({date(2026, 1, 2): 100, date(2026, 1, 3): -100})
    days = [date(2026, 1, 2), date(2026, 1, 3)]

    grid = build_error_grid(days, CUTOFF, forecasts, actuals, worst_count=1)

    assert [w.delivery_day for w in grid.worst_days] == [date(2026, 1, 2)]


def test_five_worst_days_are_listed_by_default():
    errors = {date(2026, 1, 2) + timedelta(days=i): (i + 1) * 10 for i in range(7)}
    forecasts, actuals = _scope(errors)

    grid = build_error_grid(list(errors), CUTOFF, forecasts, actuals)

    assert [w.delivery_day for w in grid.worst_days] == [
        date(2026, 1, 8),
        date(2026, 1, 7),
        date(2026, 1, 6),
        date(2026, 1, 5),
        date(2026, 1, 4),
    ]


def test_hours_are_labelled_by_uk_clock_time_not_utc():
    # 2 Jul is in British Summer Time (UTC+1), so the UK day starts at 23:00 UTC on 1 Jul. The
    # 23:00 UTC target is therefore the UK 00:00 hour of 2 Jul, which is hour 0 in the heatmap.
    day = date(2026, 7, 2)
    publish = datetime(2026, 7, 1, 7, 30)
    forecasts = [DecisionForecast(datetime(2026, 7, 1, 23, 0), publish, 5300)]
    actuals = [
        HalfHourActual(datetime(2026, 7, 1, 23, 0), 5000),
        HalfHourActual(datetime(2026, 7, 1, 23, 30), 5000),
    ]

    grid = build_error_grid([day], CUTOFF, forecasts, actuals)

    cells = {c.hour: c.error_mw for c in grid.heatmap if c.delivery_day == day}
    assert cells[0] == 300
    assert cells[23] is None
