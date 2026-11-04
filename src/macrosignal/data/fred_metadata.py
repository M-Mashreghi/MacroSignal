"""Normalize FRED series metadata and flag definition changes.

FRED's ``fred/series`` and ``fred/series/release`` records are mapped onto a
canonical :class:`SeriesMetadata`: units, frequency, seasonal adjustment,
title, source and release identity, plus the ids of the raw snapshots the
metadata was read from.

A series' *definition* (units, frequency, seasonal adjustment) can change over
time.  :func:`compare_definitions` reports such changes as
:class:`DefinitionChange` records and :func:`assert_compatible` raises
:class:`DefinitionChangeError` for blocking ones, so incompatible histories are
never merged silently.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.data.fred import FRED_PROVIDER, FredClient
from macrosignal.data.http import ResponseSchemaError
from macrosignal.domain.macro_observation import Frequency, SeasonalAdjustment
from macrosignal.domain.manifest import stable_hash

NonEmptyStr = Annotated[str, Field(min_length=1)]

_FREQUENCY = {
    "d": Frequency.DAILY,
    "daily": Frequency.DAILY,
    "w": Frequency.WEEKLY,
    "weekly": Frequency.WEEKLY,
    "m": Frequency.MONTHLY,
    "monthly": Frequency.MONTHLY,
    "q": Frequency.QUARTERLY,
    "quarterly": Frequency.QUARTERLY,
    "a": Frequency.ANNUAL,
    "annual": Frequency.ANNUAL,
}

_SEASONAL = {
    "sa": SeasonalAdjustment.SEASONALLY_ADJUSTED,
    "seasonally adjusted": SeasonalAdjustment.SEASONALLY_ADJUSTED,
    "saar": SeasonalAdjustment.SEASONALLY_ADJUSTED_ANNUAL_RATE,
    "seasonally adjusted annual rate": SeasonalAdjustment.SEASONALLY_ADJUSTED_ANNUAL_RATE,
    "nsa": SeasonalAdjustment.NOT_SEASONALLY_ADJUSTED,
    "not seasonally adjusted": SeasonalAdjustment.NOT_SEASONALLY_ADJUSTED,
}

#: Fields whose change makes histories incompatible.
DEFINITION_FIELDS = ("units", "frequency", "seasonal_adjustment")


class MetadataNormalizationError(ValueError):
    """A FRED metadata value cannot be mapped onto the canonical vocabulary."""


class SeriesMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Literal["fred_alfred"] = FRED_PROVIDER  # type: ignore[assignment]
    series_id: NonEmptyStr
    title: NonEmptyStr
    units: NonEmptyStr
    units_short: str | None = None
    frequency: Frequency
    seasonal_adjustment: SeasonalAdjustment
    observation_start: date | None = None
    observation_end: date | None = None
    last_updated: AwareDatetime | None = None
    release_id: int | None = None
    release_name: str | None = None
    metadata_snapshot_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    retrieved_at: AwareDatetime

    @property
    def definition(self) -> dict[str, str]:
        return {
            "units": self.units,
            "frequency": self.frequency.value,
            "seasonal_adjustment": self.seasonal_adjustment.value,
        }

    @property
    def definition_hash(self) -> str:
        return stable_hash(self.definition)


class DefinitionChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    series_id: str
    field: str
    previous: str | None
    current: str | None
    blocking: bool


class DefinitionChangeError(ValueError):
    """Blocking definition change between two metadata snapshots."""

    def __init__(self, changes: list[DefinitionChange]) -> None:
        detail = "; ".join(f"{c.field}: {c.previous!r} -> {c.current!r}" for c in changes)
        super().__init__(f"incompatible definition change for {changes[0].series_id}: {detail}")
        self.changes = changes


def _map(table: dict[str, Any], *candidates: Any, what: str) -> Any:
    for value in candidates:
        if isinstance(value, str) and value.strip().lower() in table:
            return table[value.strip().lower()]
    raise MetadataNormalizationError(f"unsupported {what}: {candidates!r}")


def _date(value: Any) -> date | None:
    return date.fromisoformat(value) if isinstance(value, str) and value else None


def _last_updated(value: Any) -> datetime | None:
    """Parse FRED's ``YYYY-MM-DD HH:MM:SS-05`` (offset in hours) format."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if len(text) >= 3 and text[-3] in "+-" and text[-2:].isdigit():
        text = f"{text}:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise MetadataNormalizationError(f"last_updated {value!r} has no UTC offset")
    return parsed


def normalize_series_metadata(
    series_record: dict[str, Any],
    release_record: dict[str, Any] | None,
    *,
    snapshot_ids: tuple[str, ...],
    retrieved_at: datetime,
) -> SeriesMetadata:
    try:
        series_id = series_record["id"]
        title = series_record["title"]
        units = series_record["units"]
    except KeyError as exc:
        raise ResponseSchemaError(f"FRED series record missing {exc}") from exc
    return SeriesMetadata(
        series_id=series_id,
        title=title,
        units=units,
        units_short=series_record.get("units_short"),
        frequency=_map(
            _FREQUENCY,
            series_record.get("frequency_short"),
            series_record.get("frequency"),
            what="frequency",
        ),
        seasonal_adjustment=_map(
            _SEASONAL,
            series_record.get("seasonal_adjustment_short"),
            series_record.get("seasonal_adjustment"),
            what="seasonal adjustment",
        ),
        observation_start=_date(series_record.get("observation_start")),
        observation_end=_date(series_record.get("observation_end")),
        last_updated=_last_updated(series_record.get("last_updated")),
        release_id=release_record.get("id") if release_record else None,
        release_name=release_record.get("name") if release_record else None,
        metadata_snapshot_ids=snapshot_ids,
        retrieved_at=retrieved_at,
    )


def fetch_series_metadata(
    client: FredClient, series_id: str, retrieved_at: datetime
) -> SeriesMetadata:
    """Fetch ``fred/series`` + ``fred/series/release`` and normalize them."""
    series = client.series(series_id)
    release = client.series_release(series_id)
    if len(series.records) != 1:
        raise ResponseSchemaError(f"expected exactly one series record for {series_id}")
    if len(release.records) > 1:
        raise ResponseSchemaError(f"series {series_id} maps to multiple releases")
    return normalize_series_metadata(
        series.records[0],
        release.records[0] if release.records else None,
        snapshot_ids=series.snapshot_ids + release.snapshot_ids,
        retrieved_at=retrieved_at,
    )


def compare_definitions(
    previous: SeriesMetadata, current: SeriesMetadata
) -> list[DefinitionChange]:
    """Report changes between two metadata snapshots of the same series."""
    if previous.series_id != current.series_id:
        raise ValueError("cannot compare metadata of different series")
    changes = [
        DefinitionChange(
            series_id=current.series_id,
            field=name,
            previous=previous.definition[name],
            current=current.definition[name],
            blocking=True,
        )
        for name in DEFINITION_FIELDS
        if previous.definition[name] != current.definition[name]
    ]
    for name in ("title", "release_id"):
        old, new = getattr(previous, name), getattr(current, name)
        if old != new:
            changes.append(
                DefinitionChange(
                    series_id=current.series_id,
                    field=name,
                    previous=None if old is None else str(old),
                    current=None if new is None else str(new),
                    blocking=False,
                )
            )
    return changes


def assert_compatible(previous: SeriesMetadata, current: SeriesMetadata) -> list[DefinitionChange]:
    """Raise on blocking definition changes; return non-blocking ones for logging."""
    changes = compare_definitions(previous, current)
    blocking = [c for c in changes if c.blocking]
    if blocking:
        raise DefinitionChangeError(blocking)
    return changes
