"""Validate single Elexon rows and convert them to domain records.

Every timestamp is stored as a naive datetime in UTC. Elexon sends ``Z`` timestamps, and offsets
are converted, so the snapshot never depends on a session timezone.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
    field_validator,
)

# Above the largest GB wind output ever recorded with headroom. Anything bigger is a bad row.
MAX_GENERATION_MW = 100_000

Generation = Annotated[StrictInt, Field(ge=0, le=MAX_GENERATION_MW)]


class MalformedRecordError(ValueError):
    """Raised when an Elexon row cannot become a valid record."""


@dataclass(frozen=True)
class Forecast:
    publish_time: datetime
    target_time: datetime
    generation_mw: int


@dataclass(frozen=True)
class Actual:
    target_time: datetime
    generation_mw: int


def _to_naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


class _WindforRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    publish_time: AwareDatetime = Field(alias="publishTime")
    target_time: AwareDatetime = Field(alias="startTime")
    generation: Generation

    @field_validator("publish_time", "target_time")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _to_naive_utc(value)

    @field_validator("target_time", mode="before")
    @classmethod
    def _hourly(cls, value: Any) -> Any:
        # Checked on the raw value so the offset in the string is respected.
        _require_aligned(value, minutes=(0,), label="WINDFOR startTime")
        return value


class _FuelhhRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_time: AwareDatetime = Field(alias="startTime")
    generation: Generation

    @field_validator("target_time")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _to_naive_utc(value)

    @field_validator("target_time", mode="before")
    @classmethod
    def _half_hourly(cls, value: Any) -> Any:
        _require_aligned(value, minutes=(0, 30), label="FUELHH startTime")
        return value


def _require_aligned(value: Any, minutes: tuple[int, ...], label: str) -> None:
    """Raise unless ``value`` parses to a whole second on one of ``minutes`` (in its own offset)."""
    if not isinstance(value, str):
        return  # Type errors are reported by the model itself.
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return  # Likewise for unparseable strings.
    if parsed.minute not in minutes or parsed.second or parsed.microsecond:
        raise ValueError(f"{label} must fall on minute {minutes} of the hour")


def parse_forecast(raw: object) -> Forecast:
    """Validate one WINDFOR row."""
    try:
        row = _WindforRow.model_validate(raw)
    except ValidationError as error:
        raise MalformedRecordError(str(error)) from error
    return Forecast(
        publish_time=row.publish_time,
        target_time=row.target_time,
        generation_mw=row.generation,
    )


def parse_actual(raw: object) -> Actual:
    """Validate one FUELHH row."""
    try:
        row = _FuelhhRow.model_validate(raw)
    except ValidationError as error:
        raise MalformedRecordError(str(error)) from error
    return Actual(target_time=row.target_time, generation_mw=row.generation)
