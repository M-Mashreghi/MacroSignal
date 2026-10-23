"""Canonical macro observation with reference period, release and vintage lineage.

A ``MacroObservation`` is one value of one series for one reference period as
published at one release stage / vintage. Availability is an
:class:`AvailabilityStamp`, never a naive date, so the point-in-time layer can
apply ``available_at <= decision_time`` without guessing.

Chronology checks are date-level and evaluated in the timezone of each
timestamp, matching how official sources publish release dates.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    model_validator,
)

from macrosignal.domain.availability import AvailabilityStamp

NonEmptyStr = Annotated[str, Field(min_length=1)]


class ReleaseStage(StrEnum):
    """Publication stage of a value (initial print, estimate rounds, revisions)."""

    INITIAL = "initial"
    ADVANCE = "advance"
    SECOND = "second"
    THIRD = "third"
    REVISION = "revision"
    BENCHMARK_REVISION = "benchmark_revision"


class Frequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class SeasonalAdjustment(StrEnum):
    SEASONALLY_ADJUSTED = "seasonally_adjusted"
    SEASONALLY_ADJUSTED_ANNUAL_RATE = "seasonally_adjusted_annual_rate"
    NOT_SEASONALLY_ADJUSTED = "not_seasonally_adjusted"


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _reference_period_problem(freq: Frequency, start: date, end: date) -> str | None:
    """Return why ``start``..``end`` is not a whole period of ``freq``, or None."""
    if freq is Frequency.DAILY:
        ok = start == end
    elif freq is Frequency.WEEKLY:
        ok = (end - start).days == 6
    elif freq is Frequency.MONTHLY:
        ok = start.day == 1 and end == _month_end(start.year, start.month)
    elif freq is Frequency.QUARTERLY:
        ok = (
            start.day == 1
            and start.month in (1, 4, 7, 10)
            and end == _month_end(start.year, start.month + 2)
        )
    else:
        ok = start == date(start.year, 1, 1) and end == date(start.year, 12, 31)
    if ok:
        return None
    return f"reference period {start}..{end} is not a single {freq.value} period"


class MacroObservation(BaseModel):
    """One published value of a macro series for one reference period."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Source provenance.
    source: NonEmptyStr
    series_id: NonEmptyStr
    retrieved_at: AwareDatetime
    source_snapshot_id: NonEmptyStr
    adapter_version: NonEmptyStr

    # Release identity.
    release_family: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")] | None = None
    release_id: NonEmptyStr | None = None
    release_stage: ReleaseStage

    # What was measured.
    reference_start: date
    reference_end: date
    value: FiniteFloat
    units: NonEmptyStr
    frequency: Frequency
    seasonal_adjustment: SeasonalAdjustment

    # When it became knowable.
    release_timestamp: AwareDatetime | None = None
    availability: AvailabilityStamp

    # Vintage lineage (ALFRED real-time period; realtime_end may be open, 9999-12-31).
    vintage_date: date | None = None
    realtime_start: date | None = None
    realtime_end: date | None = None

    @model_validator(mode="after")
    def _check_chronology(self) -> MacroObservation:
        problems: list[str] = []

        if self.reference_end < self.reference_start:
            problems.append("reference_end is before reference_start")
        else:
            period_problem = _reference_period_problem(
                self.frequency, self.reference_start, self.reference_end
            )
            if period_problem:
                problems.append(period_problem)

        # A value cannot be known before its reference period has ended; only
        # daily observations may become available on the reference date itself.
        available_at = self.availability.available_at
        same_day_ok = self.frequency is Frequency.DAILY

        def too_early(ts: datetime) -> bool:
            d = ts.date()
            return d < self.reference_end or (d == self.reference_end and not same_day_ok)

        if too_early(available_at):
            problems.append(
                f"availability.available_at {available_at.isoformat()} is not after the "
                f"reference period end {self.reference_end}"
            )
        if self.release_timestamp is not None:
            if too_early(self.release_timestamp):
                problems.append(
                    f"release_timestamp {self.release_timestamp.isoformat()} is not after "
                    f"the reference period end {self.reference_end}"
                )
            if available_at < self.release_timestamp:
                problems.append(
                    "availability.available_at precedes release_timestamp; availability "
                    "may only be shifted later than the release, never earlier"
                )

        if self.retrieved_at < available_at:
            problems.append("retrieved_at precedes availability.available_at")

        if self.realtime_end is not None and self.realtime_start is None:
            problems.append("realtime_end requires realtime_start")
        if (
            self.realtime_start is not None
            and self.realtime_end is not None
            and self.realtime_end < self.realtime_start
        ):
            problems.append("realtime_end is before realtime_start")

        available_date = available_at.date()
        for name in ("vintage_date", "realtime_start"):
            lineage_date = getattr(self, name)
            if lineage_date is not None and available_date < lineage_date:
                problems.append(
                    f"availability.available_at {available_at.isoformat()} is before "
                    f"{name} {lineage_date}"
                )
            if lineage_date is not None and lineage_date < self.reference_end:
                problems.append(f"{name} {lineage_date} is before reference_end")

        if problems:
            raise ValueError("; ".join(problems))
        return self

    def is_available_at(self, decision_time: datetime) -> bool:
        """Return whether this observation is knowable at ``decision_time``."""
        return self.availability.is_available_at(decision_time)
