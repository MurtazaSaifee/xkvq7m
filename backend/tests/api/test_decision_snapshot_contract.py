from pathlib import Path

import httpx
import pytest

from app.core.config import SNAPSHOT_PATH_ENV
from app.main import create_app

PROBLEM_MEDIA_TYPE = "application/problem+json"


@pytest.fixture
def api(decision_snapshot: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.AsyncClient:
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(decision_snapshot))
    transport = httpx.ASGITransport(app=create_app())
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_decision_snapshot_returns_the_hourly_forecasts_and_half_hourly_actuals(
    api: httpx.AsyncClient,
):
    async with api:
        response = await api.get("/api/v1/decision-snapshot", params={"delivery_day": "2026-01-02"})

    assert response.status_code == 200
    body = response.json()
    assert body["delivery_day"] == "2026-01-02"
    assert body["decision_day"] == "2026-01-01"
    assert body["cutoff"] == "09:20"
    assert body["cutoff_time"] == "2026-01-01T09:20:00Z"
    assert body["forecast_run_publish_time"] == "2026-01-01T09:20:00Z"
    assert len(body["hours"]) == 24
    assert len(body["actuals"]) == 48


async def test_each_hour_carries_its_forecast_aligned_actual_and_error(api: httpx.AsyncClient):
    async with api:
        body = (
            await api.get("/api/v1/decision-snapshot", params={"delivery_day": "2026-01-02"})
        ).json()

    # 00:00 forecast 10100 (published exactly at the cutoff), actual mean of 14000 and 14200.
    assert body["hours"][0] == {
        "target_time": "2026-01-02T00:00:00Z",
        "publish_time": "2026-01-01T09:20:00Z",
        "forecast_mw": 10100.0,
        "actual_mw": 14100.0,
        "error_mw": -4000.0,
    }
    # 01:00 has no decision forecast and no actual: a gap, not an error.
    assert body["hours"][1] == {
        "target_time": "2026-01-02T01:00:00Z",
        "publish_time": None,
        "forecast_mw": None,
        "actual_mw": None,
        "error_mw": None,
    }


async def test_actuals_are_half_hourly_and_missing_slots_are_null(api: httpx.AsyncClient):
    async with api:
        body = (
            await api.get("/api/v1/decision-snapshot", params={"delivery_day": "2026-01-02"})
        ).json()

    assert body["actuals"][0] == {"target_time": "2026-01-02T00:00:00Z", "generation_mw": 14000.0}
    assert body["actuals"][1] == {"target_time": "2026-01-02T00:30:00Z", "generation_mw": 14200.0}
    assert body["actuals"][2] == {"target_time": "2026-01-02T01:00:00Z", "generation_mw": None}


async def test_day_kpis_cover_only_the_hours_with_both_a_forecast_and_an_actual(
    api: httpx.AsyncClient,
):
    async with api:
        body = (
            await api.get("/api/v1/decision-snapshot", params={"delivery_day": "2026-01-02"})
        ).json()

    assert body["kpis"] == {
        "forecast_mwh": 10100.0,
        "actual_mwh": 14100.0,
        "error_mwh": -4000.0,
        "paired_hours": 1,
        "missing_forecast_hours": 20,
        "missing_actual_hours": 23,
    }


async def test_the_default_cutoff_is_0920_and_an_explicit_cutoff_is_used(api: httpx.AsyncClient):
    async with api:
        default = (
            await api.get("/api/v1/decision-snapshot", params={"delivery_day": "2026-01-02"})
        ).json()
        later = (
            await api.get(
                "/api/v1/decision-snapshot",
                params={"delivery_day": "2026-01-02", "cutoff": "09:50"},
            )
        ).json()

    assert default["cutoff"] == "09:20"
    assert later["cutoff"] == "09:50"
    # At 09:50, 00:00 picks up the 09:50 run, and 01:00 gains the 09:30 run it lacked at 09:20.
    assert later["hours"][0]["forecast_mw"] == 10200.0
    assert default["hours"][1]["forecast_mw"] is None
    assert later["hours"][1]["forecast_mw"] == 9000.0


@pytest.mark.parametrize("delivery_day", ["2026-01-02", "2026-02-01"])
async def test_the_first_and_last_delivery_days_in_scope_are_served(
    api: httpx.AsyncClient, delivery_day: str
):
    async with api:
        response = await api.get("/api/v1/decision-snapshot", params={"delivery_day": delivery_day})

    assert response.status_code == 200
    assert response.json()["delivery_day"] == delivery_day


@pytest.mark.parametrize(
    ("params", "problem_type_suffix"),
    [
        ({"delivery_day": "2026-02-30"}, "invalid-parameter"),
        ({"delivery_day": "not-a-date"}, "invalid-parameter"),
        ({}, "invalid-parameter"),
        ({"delivery_day": "2026-02-01", "cutoff": "9:20"}, "invalid-parameter"),
        ({"delivery_day": "2026-02-01", "cutoff": "24:00"}, "invalid-parameter"),
        ({"delivery_day": "2026-02-01", "cutoff": "09:20:00"}, "invalid-parameter"),
        ({"delivery_day": "2026-01-01"}, "delivery-day-out-of-range"),
        ({"delivery_day": "2026-02-02"}, "delivery-day-out-of-range"),
    ],
)
async def test_invalid_or_out_of_range_requests_return_rfc_7807_problems(
    api: httpx.AsyncClient, params: dict[str, str], problem_type_suffix: str
):
    async with api:
        response = await api.get("/api/v1/decision-snapshot", params=params)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    problem = response.json()
    assert problem["status"] == 422
    assert problem["type"].endswith(problem_type_suffix)
    assert problem["title"]
    assert problem["detail"]
    assert problem["instance"] == "/api/v1/decision-snapshot"


async def test_a_missing_snapshot_is_a_503_problem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(SNAPSHOT_PATH_ENV, str(tmp_path / "absent.duckdb"))
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/decision-snapshot", params={"delivery_day": "2026-01-02"}
        )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert response.json()["status"] == 503


async def test_unknown_routes_also_return_problem_json(api: httpx.AsyncClient):
    async with api:
        response = await api.get("/api/v1/no-such-route")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)


async def test_openapi_documents_the_decision_snapshot_route_and_its_parameters():
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        document = (await client.get("/openapi.json")).json()

    operation = document["paths"]["/api/v1/decision-snapshot"]["get"]
    parameter_names = {p["name"] for p in operation["parameters"]}
    assert parameter_names == {"delivery_day", "cutoff"}
    assert PROBLEM_MEDIA_TYPE in operation["responses"]["422"]["content"]
    assert PROBLEM_MEDIA_TYPE in operation["responses"]["503"]["content"]
