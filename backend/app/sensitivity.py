"""Print the alignment sensitivity check at the default cutoff, from the snapshot in use.

``make sensitivity`` runs this module. It reads the figures from the accuracy endpoint, the same
response the Accuracy and Methodology views use, so the printed numbers are the ones in the app.
"""

import asyncio
import logging
from typing import Any

import httpx

from app.domain.decision import DEFAULT_CUTOFF
from app.main import create_app

LABEL_WIDTH = 16
COLUMN_WIDTH = 14
# Each row is the label, then the response key and whether the value is a whole count.
ROWS: tuple[tuple[str, str, bool], ...] = (
    ("Measured hours", "measured_hours", True),
    ("MAE (MW)", "mae_mw", False),
    ("Bias (MW)", "bias_mw", False),
    ("RMSE (MW)", "rmse_mw", False),
)


def _cell(value: float | int | None, count: bool) -> str:
    if value is None:
        return "-"
    return f"{value}" if count else f"{value:,.1f}"


def _difference(top: float | int | None, hourly: float | int | None, count: bool) -> str:
    """Top of hour minus hourly mean, signed. A dash where either side has no value."""
    if top is None or hourly is None:
        return "-"
    return f"{top - hourly:+d}" if count else f"{top - hourly:+,.1f}"


def render(payload: dict[str, Any]) -> str:
    """The sensitivity check as a plain-text table, from one accuracy response."""
    sensitivity = payload["alignment_sensitivity"]
    hourly: dict[str, Any] = sensitivity["hourly_mean"]
    top: dict[str, Any] = sensitivity["top_of_hour"]
    days = payload["delivery_days"]

    title = f"at the {payload['cutoff']} cutoff, {days['first']} to {days['last']}"
    lines = [
        f"Alignment sensitivity {title}",
        f"{'':<{LABEL_WIDTH}}{'hourly mean':>{COLUMN_WIDTH}}"
        f"{'top of hour':>{COLUMN_WIDTH}}{'difference':>{COLUMN_WIDTH}}",
    ]
    for label, key, count in ROWS:
        hourly_value = hourly[key]
        top_value = top[key]
        lines.append(
            f"{label:<{LABEL_WIDTH}}{_cell(hourly_value, count):>{COLUMN_WIDTH}}"
            f"{_cell(top_value, count):>{COLUMN_WIDTH}}"
            f"{_difference(top_value, hourly_value, count):>{COLUMN_WIDTH}}"
        )
    lines.append(
        "Hourly mean: the mean of each hour's two half-hours. Top of hour: the half-hour starting "
        "at h:00 alone. Each rule counts only the hours it can measure."
    )
    return "\n".join(lines)


async def _accuracy_at_default_cutoff() -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    # create_app() turns on the JSON access log, which shares stdout with the report. Keep it quiet.
    logging.getLogger().setLevel(logging.WARNING)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(
            "/api/v1/accuracy", params={"cutoff": DEFAULT_CUTOFF.strftime("%H:%M")}
        )


def main() -> None:
    response = asyncio.run(_accuracy_at_default_cutoff())
    if response.status_code != 200:
        raise SystemExit(
            f"accuracy request failed with HTTP {response.status_code}: {response.text}"
        )
    print(render(response.json()))


if __name__ == "__main__":
    main()
