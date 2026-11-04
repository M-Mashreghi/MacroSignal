"""ALFRED vintage-date retrieval and chronological revision history.

``fetch_vintage_dates`` retrieves every vintage date of a series (the dates on
which ALFRED recorded a new release or revision), validates that they form a
strictly increasing chronology, and keeps the raw snapshot ids.
``fetch_pit_vintage_dates`` does this for every PIT-required FRED series of the
macro registry, and ``persist_vintage_dates`` stores each set as an immutable
normalized artifact.

``vintage_history`` turns ALFRED observation records (all real-time periods)
into the ordered revision history of each reference date, so later revisions
never overwrite earlier vintages.

Vintage dates are *date-level* evidence: they say on which day a value was
published, not at what time (``docs/AVAILABILITY_RESOLUTION.md``).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from macrosignal.artifacts import ArtifactKind, ArtifactRecord, ArtifactRegistry
from macrosignal.config.models import MacroSeriesRegistry
from macrosignal.data.fred import FRED_PROVIDER, FredClient
from macrosignal.data.http import ResponseSchemaError
from macrosignal.domain.manifest import canonical_json, stable_hash

OPEN_REALTIME_END = date(9999, 12, 31)
MISSING_VALUE = "."

NonEmptyStr = Annotated[str, Field(min_length=1)]


class VintageDateSet(BaseModel):
    """All ALFRED vintage dates of one series, in strictly increasing order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    series_id: NonEmptyStr
    vintage_dates: tuple[date, ...] = Field(min_length=1)
    snapshot_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    retrieved_at: AwareDatetime

    @model_validator(mode="after")
    def _check(self) -> VintageDateSet:
        dates = self.vintage_dates
        if any(b <= a for a, b in zip(dates, dates[1:], strict=False)):
            raise ValueError("vintage_dates must be strictly increasing (no duplicates)")
        if dates[-1] > self.retrieved_at.date():
            raise ValueError("a vintage date cannot be after the retrieval date")
        return self

    @property
    def content_hash(self) -> str:
        return stable_hash({"series_id": self.series_id, "vintage_dates": self.vintage_dates})

    @property
    def artifact_id(self) -> str:
        return f"vintages_{self.series_id}_{self.content_hash.removeprefix('sha256:')[:16]}"

    def latest_as_of(self, day: date) -> date | None:
        """The most recent vintage on or before ``day`` (None before the first vintage)."""
        known = [d for d in self.vintage_dates if d <= day]
        return known[-1] if known else None

    def between(self, start: date, end: date) -> tuple[date, ...]:
        return tuple(d for d in self.vintage_dates if start <= d <= end)


def _parse_date(value: Any, what: str) -> date:
    if not isinstance(value, str):
        raise ResponseSchemaError(f"{what} {value!r} is not a date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ResponseSchemaError(f"{what} {value!r} is not an ISO date") from exc


def fetch_vintage_dates(
    client: FredClient, series_id: str, retrieved_at: datetime
) -> VintageDateSet:
    result = client.vintage_dates(series_id)
    dates = [_parse_date(v, "vintage date") for v in result.records]
    if not dates:
        raise ResponseSchemaError(f"no vintage dates returned for {series_id}")
    if dates != sorted(set(dates)):
        raise ResponseSchemaError(f"vintage dates for {series_id} are unsorted or duplicated")
    return VintageDateSet(
        series_id=series_id,
        vintage_dates=tuple(dates),
        snapshot_ids=result.snapshot_ids,
        retrieved_at=retrieved_at,
    )


def pit_series_ids(registry: MacroSeriesRegistry) -> list[str]:
    return sorted(
        {s.series_id for s in registry.series if s.provider == FRED_PROVIDER and s.pit_required}
    )


def fetch_pit_vintage_dates(
    client: FredClient, registry: MacroSeriesRegistry, retrieved_at: datetime
) -> dict[str, VintageDateSet]:
    return {sid: fetch_vintage_dates(client, sid, retrieved_at) for sid in pit_series_ids(registry)}


def persist_vintage_dates(registry: ArtifactRegistry, vintages: VintageDateSet) -> ArtifactRecord:
    payload = vintages.model_dump(mode="json", exclude={"retrieved_at"})
    return registry.register(
        ArtifactKind.NORMALIZED,
        vintages.artifact_id,
        {"vintage_dates.json": canonical_json(payload).encode("utf-8")},
        created_at=vintages.retrieved_at,
        metadata={"series_id": vintages.series_id, "dataset": "alfred_vintage_dates"},
    )


class VintageValue(BaseModel):
    """One value of one reference date over one ALFRED real-time period."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_date: date
    realtime_start: date
    realtime_end: date
    value: float | None  # None = ALFRED "." (no value in that vintage)

    @model_validator(mode="after")
    def _check(self) -> VintageValue:
        if self.realtime_end < self.realtime_start:
            raise ValueError("realtime_end is before realtime_start")
        return self


def vintage_history(
    records: Iterable[dict[str, Any]], vintages: VintageDateSet | None = None
) -> dict[date, list[VintageValue]]:
    """Group ALFRED observation records into per-reference-date revision chains.

    Each chain is ordered by ``realtime_start`` and must be non-overlapping.
    When ``vintages`` is given, every ``realtime_start`` must be a known vintage.
    """
    chains: dict[date, list[VintageValue]] = defaultdict(list)
    known = set(vintages.vintage_dates) if vintages is not None else None
    for rec in records:
        try:
            raw_value = rec["value"]
            value = None if raw_value == MISSING_VALUE else float(raw_value)
            item = VintageValue(
                reference_date=_parse_date(rec["date"], "date"),
                realtime_start=_parse_date(rec["realtime_start"], "realtime_start"),
                realtime_end=_parse_date(rec["realtime_end"], "realtime_end"),
                value=value,
            )
        except KeyError as exc:
            raise ResponseSchemaError(f"observation record missing {exc}") from exc
        if known is not None and item.realtime_start not in known:
            raise ResponseSchemaError(
                f"realtime_start {item.realtime_start} of {item.reference_date} is not a "
                "known vintage date"
            )
        chains[item.reference_date].append(item)
    for ref, chain in chains.items():
        chain.sort(key=lambda v: v.realtime_start)
        for prev, nxt in zip(chain, chain[1:], strict=False):
            if nxt.realtime_start <= prev.realtime_end:
                raise ResponseSchemaError(f"overlapping real-time periods for {ref}")
    return dict(sorted(chains.items()))
