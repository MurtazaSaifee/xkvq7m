from pathlib import Path
from typing import Any

import pytest

from app.core.config import SNAPSHOT_PATH_ENV
from app.sensitivity import main, render


def _payload(top_mae: float | None = 600.0) -> dict[str, Any]:
    """An accuracy response, with only the fields the sensitivity report reads."""
    return {
        "cutoff": "09:20",
        "delivery_days": {"first": "2026-01-02", "last": "2026-02-01"},
        "alignment_sensitivity": {
            "hourly_mean": {
                "measured_hours": 6,
                "mae_mw": 550.0,
                "bias_mw": 216.7,
                "rmse_mw": 641.6,
                "p90_abs_error_mw": 950.0,
                "nmae_percent": 3.6,
            },
            "top_of_hour": {
                "measured_hours": 6,
                "mae_mw": top_mae,
                "bias_mw": 266.7,
                "rmse_mw": 678.2,
                "p90_abs_error_mw": 1000.0,
                "nmae_percent": 3.9,
            },
        },
    }


def _row(text: str, label: str) -> list[str]:
    """The cells of the one line that starts with ``label``, split on whitespace."""
    lines = [line.split() for line in text.splitlines() if line.startswith(label)]
    assert len(lines) == 1, f"expected one {label!r} line in:\n{text}"
    return lines[0]


def test_render_names_the_cutoff_and_the_delivery_days_in_scope():
    text = render(_payload())

    assert text.splitlines()[0] == (
        "Alignment sensitivity at the 09:20 cutoff, 2026-01-02 to 2026-02-01"
    )


def test_render_puts_the_two_rules_side_by_side_with_the_difference():
    text = render(_payload())

    # The difference is top of hour minus hourly mean, in MW.
    assert _row(text, "MAE") == ["MAE", "(MW)", "550.0", "600.0", "+50.0"]
    assert _row(text, "Bias") == ["Bias", "(MW)", "216.7", "266.7", "+50.0"]
    assert _row(text, "Measured") == ["Measured", "hours", "6", "6", "+0"]


def test_render_adds_the_p90_and_nmae_rows_for_both_rules():
    text = render(_payload())

    assert _row(text, "P90") == ["P90", "(MW)", "950.0", "1,000.0", "+50.0"]
    assert _row(text, "nMAE") == ["nMAE", "(%)", "3.6", "3.9", "+0.3"]


def test_render_shows_a_dash_where_a_rule_has_no_measured_hour():
    text = render(_payload(top_mae=None))

    assert _row(text, "MAE") == ["MAE", "(MW)", "550.0", "-", "-"]


@pytest.mark.parametrize("label", ["hourly mean", "top of hour", "difference"])
def test_render_labels_both_rules_and_the_difference_column(label: str):
    assert label in render(_payload()).splitlines()[1]


def test_main_prints_the_check_from_the_snapshot_in_use(
    decision_snapshot: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(decision_snapshot))

    main()

    out = capsys.readouterr().out
    assert "Alignment sensitivity at the 09:20 cutoff" in out
    assert "top of hour" in out
