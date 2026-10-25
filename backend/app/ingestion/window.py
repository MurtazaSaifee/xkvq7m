"""The fixed date window that ``make ingest`` fetches. All datetimes are naive UTC."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class IngestionWindow:
    windfor_publish_from: datetime
    windfor_publish_to: datetime
    fuelhh_settlement_from: date
    fuelhh_settlement_to: date
    delivery_day_first: date
    delivery_day_last: date


# WINDFOR starts 14 delivery days before 2 Jan so the walk-forward error band has its warm-up.
# FUELHH starts on 19 Dec for the same reason. Both end so that every forecast for a target time
# up to the end of 1 Feb is present.
DEFAULT_WINDOW = IngestionWindow(
    windfor_publish_from=datetime(2025, 12, 18, 0, 0),
    windfor_publish_to=datetime(2026, 2, 1, 23, 59),
    fuelhh_settlement_from=date(2025, 12, 19),
    fuelhh_settlement_to=date(2026, 2, 1),
    delivery_day_first=date(2026, 1, 2),
    delivery_day_last=date(2026, 2, 1),
)
