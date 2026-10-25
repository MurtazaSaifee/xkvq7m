from datetime import date, datetime, time

import pytest

from app.domain.decision import DEFAULT_CUTOFF, decision_cutoff_instant, parse_cutoff


def test_default_cutoff_is_the_epex_0920_auction():
    assert time(9, 20) == DEFAULT_CUTOFF


def test_cutoff_is_on_the_decision_day_the_day_before_delivery():
    # Delivery 2 Jan 2026 is decided on 1 Jan 2026. January is GMT, so 09:20 UK is 09:20 UTC.
    assert decision_cutoff_instant(date(2026, 1, 2), time(9, 20)) == datetime(2026, 1, 1, 9, 20)


def test_cutoff_crosses_the_month_boundary():
    assert decision_cutoff_instant(date(2026, 2, 1), time(9, 20)) == datetime(2026, 1, 31, 9, 20)


def test_cutoff_in_british_summer_time_is_converted_to_utc():
    # Summer time is UTC+1, so 09:20 BST is 08:20 UTC.
    assert decision_cutoff_instant(date(2026, 7, 2), time(9, 20)) == datetime(2026, 7, 1, 8, 20)


def test_parse_cutoff_reads_hh_mm():
    assert parse_cutoff("14:30") == time(14, 30)


@pytest.mark.parametrize("text", ["9:20", "24:00", "09:60", "0920", "09:20:00", ""])
def test_parse_cutoff_rejects_anything_that_is_not_hh_mm(text: str):
    with pytest.raises(ValueError):
        parse_cutoff(text)
