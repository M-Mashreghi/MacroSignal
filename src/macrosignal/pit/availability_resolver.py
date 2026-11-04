"""Availability resolver and precision hierarchy.

Takes normalized observations (typically ALFRED vintages with date-level,
end-of-day availability) plus official release-calendar events and emits a
final, audited availability for each one:

1. **official_calendar_exact** - the versioned release mapping
   (:class:`~macrosignal.pit.release_mapping.ReleaseMappingRegistry`) finds a
   unique *released* calendar event for the observation's family, reference
   period and stage, whose local release date equals the vintage date.  The
   stamp becomes ``exact_timestamp`` at the event's actual release time, citing
   ``calendar_mapping_id = <mapping id>/<calendar snapshot>/<release id>``.
2. **source_stamp** - the observation already carries exact/provider-level
   availability from its own source; it is kept unchanged.
3. **vintage_date_conservative_eod** - only a date is known: availability is
   placed at the end of that date in America/New_York (never earlier than the
   incoming stamp).  Ambiguous or conflicting calendar evidence is *rejected*
   and also lands here, with the reason recorded.
4. **unknown** - no usable timing evidence; flagged so experiments can exclude it.

Precision hierarchy (best first): ``exact_timestamp > provider_timestamp >
release_date_only > inferred_eod > unknown``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, time
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from macrosignal.domain import (
    DATE_LEVEL_PRECISIONS,
    AvailabilityPrecision,
    AvailabilitySource,
    AvailabilityStamp,
    MacroObservation,
    ReleaseEvent,
)
from macrosignal.pit.release_mapping import (
    AmbiguousMappingError,
    MappingConflictError,
    ReleaseMappingRegistry,
)

RESOLVER_VERSION = "availability-resolver-1"
DEFAULT_DATE_TIMEZONE = ZoneInfo("America/New_York")
END_OF_DAY = time(23, 59, 59)

PRECISION_RANK: dict[AvailabilityPrecision, int] = {
    AvailabilityPrecision.EXACT_TIMESTAMP: 0,
    AvailabilityPrecision.PROVIDER_TIMESTAMP: 1,
    AvailabilityPrecision.RELEASE_DATE_ONLY: 2,
    AvailabilityPrecision.INFERRED_EOD: 3,
    AvailabilityPrecision.UNKNOWN: 4,
}


def meets_precision(precision: AvailabilityPrecision, minimum: AvailabilityPrecision) -> bool:
    """Whether ``precision`` is at least as good as ``minimum``."""
    return PRECISION_RANK[precision] <= PRECISION_RANK[minimum]


class ResolutionRule(StrEnum):
    OFFICIAL_CALENDAR_EXACT = "official_calendar_exact"
    SOURCE_STAMP = "source_stamp"
    VINTAGE_DATE_CONSERVATIVE_EOD = "vintage_date_conservative_eod"
    UNKNOWN = "unknown"


class ResolvedObservation(BaseModel):
    """An observation with its final availability and the audit of how it was resolved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation: MacroObservation
    rule: ResolutionRule
    raw_timing: dict[str, Any]
    release_id: str | None = None
    rejected_mapping_reason: str | None = None
    resolver_version: str = RESOLVER_VERSION

    @property
    def availability(self) -> AvailabilityStamp:
        return self.observation.availability

    @property
    def precision(self) -> AvailabilityPrecision:
        return self.observation.availability.precision


def _with_availability(
    obs: MacroObservation, stamp: AvailabilityStamp, release_timestamp: datetime | None
) -> MacroObservation:
    data = obs.model_dump()
    data["availability"] = stamp.model_dump()
    if release_timestamp is not None:
        data["release_timestamp"] = release_timestamp
    return MacroObservation.model_validate(data)


class AvailabilityResolver:
    def __init__(
        self,
        mapping: ReleaseMappingRegistry,
        events: Iterable[ReleaseEvent],
        *,
        resolver_version: str = RESOLVER_VERSION,
        date_timezone: ZoneInfo = DEFAULT_DATE_TIMEZONE,
    ) -> None:
        self.mapping = mapping
        self.events: Sequence[ReleaseEvent] = tuple(events)
        self.resolver_version = resolver_version
        self.date_timezone = date_timezone

    def _raw_timing(self, obs: MacroObservation) -> dict[str, Any]:
        s = obs.availability
        return {
            "available_at": s.available_at.isoformat(),
            "precision": s.precision.value,
            "availability_source": s.availability_source.value if s.availability_source else None,
            "raw_available_date": s.raw_available_date.isoformat()
            if s.raw_available_date
            else None,
            "vintage_date": obs.vintage_date.isoformat() if obs.vintage_date else None,
        }

    def _conservative(self, obs: MacroObservation) -> AvailabilityStamp | None:
        s = obs.availability
        raw_date = s.raw_available_date or obs.vintage_date or obs.realtime_start
        if raw_date is None:
            return None
        eod = datetime.combine(raw_date, END_OF_DAY, tzinfo=self.date_timezone)
        midnight = datetime.combine(raw_date, time(0, 0), tzinfo=self.date_timezone)
        available_at = max(eod, s.available_at)  # never move earlier than the incoming stamp
        source = s.availability_source or AvailabilitySource.ALFRED_VINTAGE_DATE
        if source not in (
            AvailabilitySource.ALFRED_VINTAGE_DATE,
            AvailabilitySource.OFFICIAL_RELEASE_DATE,
        ):
            source = AvailabilitySource.ALFRED_VINTAGE_DATE
        return AvailabilityStamp(
            available_at=available_at,
            precision=AvailabilityPrecision.RELEASE_DATE_ONLY,
            availability_source=source,
            raw_available_date=raw_date,
            conservative_adjustment=available_at - midnight,
            resolver_version=self.resolver_version,
        )

    def resolve(self, obs: MacroObservation) -> ResolvedObservation:
        raw = self._raw_timing(obs)
        rejected: str | None = None
        try:
            event = self.mapping.match_event(obs, self.events)
        except (AmbiguousMappingError, MappingConflictError) as exc:
            event, rejected = None, str(exc)
        except KeyError as exc:  # series not in the mapping registry
            event, rejected = None, str(exc)

        if event is not None and event.actual_release_at is not None:
            stamp = AvailabilityStamp(
                available_at=event.actual_release_at,
                precision=AvailabilityPrecision.EXACT_TIMESTAMP,
                availability_source=obs.availability.availability_source
                if obs.availability.availability_source
                in (
                    AvailabilitySource.ALFRED_VINTAGE_DATE,
                    AvailabilitySource.OFFICIAL_RELEASE_DATE,
                )
                else AvailabilitySource.ALFRED_VINTAGE_DATE,
                raw_available_date=obs.vintage_date
                or event.actual_release_at.astimezone(event.zone).date(),
                calendar_mapping_id=(
                    f"{self.mapping.mapping_id}/{event.calendar_snapshot_id}/{event.release_id}"
                ),
                resolver_version=self.resolver_version,
            )
            return ResolvedObservation(
                observation=_with_availability(obs, stamp, event.actual_release_at),
                rule=ResolutionRule.OFFICIAL_CALENDAR_EXACT,
                raw_timing=raw,
                release_id=event.release_id,
                resolver_version=self.resolver_version,
            )

        precision = obs.availability.precision
        if precision in (
            AvailabilityPrecision.EXACT_TIMESTAMP,
            AvailabilityPrecision.PROVIDER_TIMESTAMP,
        ):
            return ResolvedObservation(
                observation=obs,
                rule=ResolutionRule.SOURCE_STAMP,
                raw_timing=raw,
                rejected_mapping_reason=rejected,
                resolver_version=self.resolver_version,
            )
        if precision in DATE_LEVEL_PRECISIONS:
            stamp_or_none = self._conservative(obs)
            if stamp_or_none is not None:
                return ResolvedObservation(
                    observation=_with_availability(obs, stamp_or_none, None),
                    rule=ResolutionRule.VINTAGE_DATE_CONSERVATIVE_EOD,
                    raw_timing=raw,
                    rejected_mapping_reason=rejected,
                    resolver_version=self.resolver_version,
                )
        return ResolvedObservation(
            observation=obs,
            rule=ResolutionRule.UNKNOWN,
            raw_timing=raw,
            rejected_mapping_reason=rejected,
            resolver_version=self.resolver_version,
        )

    def resolve_all(self, observations: Iterable[MacroObservation]) -> list[ResolvedObservation]:
        return [self.resolve(o) for o in observations]
