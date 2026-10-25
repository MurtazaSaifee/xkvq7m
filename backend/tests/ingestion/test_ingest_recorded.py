import json
import logging
from datetime import date, datetime
from pathlib import Path

import duckdb
import httpx
import pytest

from app.ingestion.elexon import IngestionError
from app.ingestion.run import run_ingestion
from app.ingestion.window import IngestionWindow

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "elexon"

# A window that covers the recorded samples: one WINDFOR run and one day of FUELHH.
RECORDED_WINDOW = IngestionWindow(
    windfor_publish_from=datetime(2026, 1, 1, 0, 0),
    windfor_publish_to=datetime(2026, 1, 1, 12, 0),
    fuelhh_settlement_from=date(2026, 1, 1),
    fuelhh_settlement_to=date(2026, 1, 1),
    delivery_day_first=date(2026, 1, 2),
    delivery_day_last=date(2026, 1, 2),
)


def recorded_transport(
    windfor: list[object] | None = None,
    fuelhh: list[object] | None = None,
) -> httpx.MockTransport:
    """Serve the recorded samples, optionally with extra rows appended to one of them."""
    windfor_rows = (
        windfor
        if windfor is not None
        else json.loads((FIXTURES / "windfor_stream_sample.json").read_text(encoding="utf-8"))
    )
    fuelhh_rows = (
        fuelhh
        if fuelhh is not None
        else json.loads((FIXTURES / "fuelhh_stream_sample.json").read_text(encoding="utf-8"))
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/WINDFOR/stream"):
            return httpx.Response(200, json=windfor_rows)
        if request.url.path.endswith("/FUELHH/stream"):
            return httpx.Response(200, json=fuelhh_rows)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_recorded_samples_are_cleaned_and_summarised(tmp_path: Path):
    output = tmp_path / "snapshot.duckdb"

    snapshot = run_ingestion(output, RECORDED_WINDOW, transport=recorded_transport())

    summary = snapshot.summary
    assert summary.forecast_rows_received == 12
    assert summary.forecast_rows_malformed == 0
    assert summary.forecast_duplicates_removed == 0
    # Eleven of the twelve rows were published after their target time (the run is 07:30Z).
    assert summary.excluded_forecasts == 11
    assert summary.forecast_gap_hours == 0
    assert summary.actual_rows_received == 12
    # 48 half-hours on 1 Jan, 12 recorded.
    assert summary.actual_gap_periods == 36
    assert output.is_file()


def test_bad_and_duplicate_rows_in_a_response_are_counted_not_stored(tmp_path: Path):
    recorded = json.loads((FIXTURES / "windfor_stream_sample.json").read_text(encoding="utf-8"))
    extra = [
        recorded[-1],  # duplicate
        {
            "dataset": "WINDFOR",
            "publishTime": "2026-01-01T07:30:00Z",
            "startTime": "2026-01-01T08:00:00",
        },
    ]

    snapshot = run_ingestion(
        tmp_path / "snapshot.duckdb",
        RECORDED_WINDOW,
        transport=recorded_transport(windfor=recorded + extra),
    )

    assert snapshot.summary.forecast_duplicates_removed == 1
    assert snapshot.summary.forecast_rows_malformed == 1
    assert len(snapshot.forecasts) == 1


def test_logs_the_validation_summary(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="app.ingestion")

    run_ingestion(tmp_path / "snapshot.duckdb", RECORDED_WINDOW, transport=recorded_transport())

    (record,) = [r for r in caplog.records if r.getMessage() == "ingestion validation summary"]
    validation: dict[str, int] = getattr(record, "validation")  # noqa: B009
    assert validation["excluded_forecasts"] == 11


def test_the_written_file_matches_the_returned_summary(tmp_path: Path):
    output = tmp_path / "snapshot.duckdb"

    snapshot = run_ingestion(output, RECORDED_WINDOW, transport=recorded_transport())

    con = duckdb.connect(str(output), read_only=True)
    try:
        metadata = con.execute("SELECT excluded_forecasts FROM ingestion_metadata").fetchone()
        stored_rows = con.execute("SELECT count(*) FROM forecasts").fetchone()
    finally:
        con.close()
    assert metadata is not None and stored_rows is not None
    assert metadata[0] == snapshot.summary.excluded_forecasts
    assert stored_rows[0] == len(snapshot.forecasts)


def test_an_unexpected_body_fails_the_run_and_leaves_no_snapshot(tmp_path: Path):
    output = tmp_path / "snapshot.duckdb"
    failing = httpx.MockTransport(lambda _: httpx.Response(200, json={"data": []}))

    with pytest.raises(IngestionError, match="expected a list"):
        run_ingestion(output, RECORDED_WINDOW, transport=failing)

    assert not output.exists()
