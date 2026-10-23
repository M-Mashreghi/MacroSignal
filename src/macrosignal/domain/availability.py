"""Availability stamp: when a value became knowable, and how precisely.

This is the minimal contract required by ``MacroObservation`` (Task 1.4).
Task 1.5 extends it with the remaining audit fields from
``docs/DATA_CONTRACT.md`` (availability source, raw available date, calendar
mapping id, resolver version, conservative adjustment) and adds ``ReleaseEvent``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict


class AvailabilityPrecision(StrEnum):
    """How precisely ``available_at`` is known (docs/AVAILABILITY_RESOLUTION.md)."""

    EXACT_TIMESTAMP = "exact_timestamp"
    PROVIDER_TIMESTAMP = "provider_timestamp"
    RELEASE_DATE_ONLY = "release_date_only"
    INFERRED_EOD = "inferred_eod"
    UNKNOWN = "unknown"


class AvailabilityStamp(BaseModel):
    """A timezone-aware availability instant with explicit precision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    available_at: AwareDatetime
    precision: AvailabilityPrecision

    def is_available_at(self, decision_time: datetime) -> bool:
        """Return whether the value is knowable at ``decision_time`` (PIT golden rule)."""
        if decision_time.tzinfo is None or decision_time.utcoffset() is None:
            raise ValueError("decision_time must be timezone-aware")
        return self.available_at <= decision_time
