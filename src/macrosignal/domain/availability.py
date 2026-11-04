"""Availability stamp: when a value became knowable, how precisely, and why.

``AvailabilityStamp`` is the canonical availability contract from
``docs/DATA_CONTRACT.md`` / ``docs/AVAILABILITY_RESOLUTION.md``. Task 1.4
introduced the minimal ``available_at`` + ``precision`` pair; Task 1.5 adds the
audit/provenance fields (availability source, raw source date, calendar mapping
id, resolver version, conservative adjustment) and the consistency rules that
stop a date-level source from masquerading as an exact timestamp.

The audit fields are optional so that a minimal stamp stays valid, but whenever
they are supplied they must be mutually consistent.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

NonEmptyStr = Annotated[str, Field(min_length=1)]


class AvailabilityPrecision(StrEnum):
    """How precisely ``available_at`` is known (docs/AVAILABILITY_RESOLUTION.md)."""

    EXACT_TIMESTAMP = "exact_timestamp"
    PROVIDER_TIMESTAMP = "provider_timestamp"
    RELEASE_DATE_ONLY = "release_date_only"
    INFERRED_EOD = "inferred_eod"
    UNKNOWN = "unknown"


#: Precisions whose source evidence is a calendar date, not an instant.
DATE_LEVEL_PRECISIONS = frozenset(
    {AvailabilityPrecision.RELEASE_DATE_ONLY, AvailabilityPrecision.INFERRED_EOD}
)


class AvailabilitySource(StrEnum):
    """Where the availability evidence came from."""

    #: Official BLS/BEA/Fed/Treasury schedule or release record with date + time + tz.
    OFFICIAL_RELEASE_SCHEDULE = "official_release_schedule"
    #: Vendor/source event timestamp with documented semantics.
    PROVIDER_TIMESTAMP = "provider_timestamp"
    #: ALFRED vintage / real-time-start date (date-level only).
    ALFRED_VINTAGE_DATE = "alfred_vintage_date"
    #: Official release date without a time of day.
    OFFICIAL_RELEASE_DATE = "official_release_date"
    #: Conservative rule-based inference (e.g. end-of-day for late-day data).
    CONSERVATIVE_INFERENCE = "conservative_inference"
    UNKNOWN = "unknown"


#: Which precisions each source can justify on its own.  Exact timestamps from a
#: date-level source additionally require a versioned calendar mapping.
_ALLOWED_PRECISIONS: dict[AvailabilitySource, frozenset[AvailabilityPrecision]] = {
    AvailabilitySource.OFFICIAL_RELEASE_SCHEDULE: frozenset(
        {AvailabilityPrecision.EXACT_TIMESTAMP}
    ),
    AvailabilitySource.PROVIDER_TIMESTAMP: frozenset({AvailabilityPrecision.PROVIDER_TIMESTAMP}),
    AvailabilitySource.ALFRED_VINTAGE_DATE: frozenset(
        {
            AvailabilityPrecision.RELEASE_DATE_ONLY,
            AvailabilityPrecision.INFERRED_EOD,
            AvailabilityPrecision.EXACT_TIMESTAMP,  # only with calendar_mapping_id
        }
    ),
    AvailabilitySource.OFFICIAL_RELEASE_DATE: frozenset(
        {
            AvailabilityPrecision.RELEASE_DATE_ONLY,
            AvailabilityPrecision.INFERRED_EOD,
            AvailabilityPrecision.EXACT_TIMESTAMP,  # only with calendar_mapping_id
        }
    ),
    AvailabilitySource.CONSERVATIVE_INFERENCE: frozenset(
        {AvailabilityPrecision.INFERRED_EOD, AvailabilityPrecision.UNKNOWN}
    ),
    AvailabilitySource.UNKNOWN: frozenset({AvailabilityPrecision.UNKNOWN}),
}

_DATE_LEVEL_SOURCES = frozenset(
    {AvailabilitySource.ALFRED_VINTAGE_DATE, AvailabilitySource.OFFICIAL_RELEASE_DATE}
)


class AvailabilityStamp(BaseModel):
    """A timezone-aware availability instant with explicit precision and provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    available_at: AwareDatetime
    precision: AvailabilityPrecision

    # Audit / provenance (docs/AVAILABILITY_RESOLUTION.md "Audit").
    availability_source: AvailabilitySource | None = None
    raw_available_date: date | None = None
    calendar_mapping_id: NonEmptyStr | None = None
    resolver_version: NonEmptyStr | None = None
    conservative_adjustment: timedelta = timedelta(0)

    @model_validator(mode="after")
    def _check_consistency(self) -> AvailabilityStamp:
        problems: list[str] = []

        if self.conservative_adjustment < timedelta(0):
            problems.append(
                "conservative_adjustment must be non-negative; availability may only be "
                "shifted later, never earlier"
            )

        source = self.availability_source
        if source is not None:
            if self.precision not in _ALLOWED_PRECISIONS[source]:
                problems.append(
                    f"precision {self.precision.value!r} is not supported by availability "
                    f"source {source.value!r}"
                )
            elif (
                source in _DATE_LEVEL_SOURCES
                and self.precision is AvailabilityPrecision.EXACT_TIMESTAMP
                and self.calendar_mapping_id is None
            ):
                problems.append(
                    f"availability source {source.value!r} is date-level; an exact_timestamp "
                    "requires a versioned calendar_mapping_id"
                )

        if self.calendar_mapping_id is not None and self.resolver_version is None:
            problems.append("calendar_mapping_id requires resolver_version")

        raw = self.raw_available_date
        if raw is not None:
            local = self.available_at
            if local.date() < raw:
                problems.append(
                    f"available_at {local.isoformat()} is before raw_available_date {raw}"
                )
            elif (
                self.precision in DATE_LEVEL_PRECISIONS
                and local.date() == raw
                and local.timetz().replace(tzinfo=None) == time(0, 0)
            ):
                problems.append(
                    "a date-only source must not be treated as midnight knowledge; "
                    f"available_at {local.isoformat()} is the start of raw_available_date"
                )

        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def raw_available_at(self) -> datetime:
        """``available_at`` before the conservative adjustment was applied."""
        return self.available_at - self.conservative_adjustment

    def is_available_at(self, decision_time: datetime) -> bool:
        """Return whether the value is knowable at ``decision_time`` (PIT golden rule)."""
        if decision_time.tzinfo is None or decision_time.utcoffset() is None:
            raise ValueError("decision_time must be timezone-aware")
        return self.available_at <= decision_time
