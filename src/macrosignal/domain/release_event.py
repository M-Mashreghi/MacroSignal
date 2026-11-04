"""Timezone-aware release events with separate scheduled and actual times.

A ``ReleaseEvent`` is one entry of a release calendar snapshot
(``docs/RELEASE_CALENDAR_SPEC.md``): a CPI print, a GDP estimate round, an FOMC
statement.  The *scheduled* time is what the calendar announced in advance; the
*actual* time is when the release was observed to happen.  They are stored
separately because a schedule is not evidence of publication, and only the
actual release time may become an availability stamp.

Timestamps must be timezone-aware; the source timezone must be an IANA
timezone-database name (never a fixed UTC offset) so DST is handled by the
database rather than guessed.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from macrosignal.domain.availability import (
    AvailabilityPrecision,
    AvailabilitySource,
    AvailabilityStamp,
)
from macrosignal.domain.macro_observation import ReleaseStage

NonEmptyStr = Annotated[str, Field(min_length=1)]

_UTC_ALIASES = frozenset({"UTC", "Etc/UTC"})


def _validate_iana_timezone(name: str) -> str:
    if name.startswith("Etc/GMT") or name.upper().startswith(("UTC+", "UTC-", "GMT+", "GMT-")):
        raise ValueError(
            f"source_timezone {name!r} is a fixed UTC offset; use an IANA zone such as "
            "'America/New_York'"
        )
    if name not in _UTC_ALIASES and "/" not in name:
        raise ValueError(f"source_timezone {name!r} is not an IANA region/city zone name")
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"source_timezone {name!r} is not in the timezone database") from exc
    return name


class ReleaseEvent(BaseModel):
    """One scheduled (and possibly realised) release from a calendar snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Identity / provenance.
    release_id: NonEmptyStr
    release_family: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")]
    release_name: NonEmptyStr
    source: NonEmptyStr
    calendar_snapshot_id: NonEmptyStr

    # Timing.
    source_timezone: NonEmptyStr
    scheduled_at: AwareDatetime
    actual_release_at: AwareDatetime | None = None

    # What is being released (optional: e.g. FOMC statements have no reference period).
    reference_start: date | None = None
    reference_end: date | None = None
    release_stage: ReleaseStage | None = None

    @field_validator("source_timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        return _validate_iana_timezone(value)

    @model_validator(mode="after")
    def _check_chronology(self) -> ReleaseEvent:
        problems: list[str] = []

        if (self.reference_start is None) != (self.reference_end is None):
            problems.append("reference_start and reference_end must be given together")
        elif self.reference_start is not None and self.reference_end is not None:
            if self.reference_end < self.reference_start:
                problems.append("reference_end is before reference_start")
            for name in ("scheduled_at", "actual_release_at"):
                ts: datetime | None = getattr(self, name)
                if ts is not None and self._local(ts).date() <= self.reference_end:
                    problems.append(
                        f"{name} {ts.isoformat()} is not after the reference period end "
                        f"{self.reference_end}"
                    )

        if problems:
            raise ValueError("; ".join(problems))
        return self

    # --- timezone views -------------------------------------------------------
    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.source_timezone)

    def _local(self, ts: datetime) -> datetime:
        return ts.astimezone(self.zone)

    @property
    def scheduled_at_utc(self) -> datetime:
        return self.scheduled_at.astimezone(ZoneInfo("UTC"))

    @property
    def scheduled_at_local(self) -> datetime:
        return self._local(self.scheduled_at)

    @property
    def actual_release_at_utc(self) -> datetime | None:
        if self.actual_release_at is None:
            return None
        return self.actual_release_at.astimezone(ZoneInfo("UTC"))

    @property
    def actual_release_at_local(self) -> datetime | None:
        if self.actual_release_at is None:
            return None
        return self._local(self.actual_release_at)

    # --- release status -------------------------------------------------------
    @property
    def is_released(self) -> bool:
        """Whether an actual release time has been recorded."""
        return self.actual_release_at is not None

    @property
    def deviation_from_schedule(self) -> float | None:
        """Actual minus scheduled time in seconds (positive = late), if released."""
        if self.actual_release_at is None:
            return None
        return (self.actual_release_at - self.scheduled_at).total_seconds()

    def to_availability_stamp(self, *, resolver_version: str) -> AvailabilityStamp:
        """Build an exact availability stamp from the *actual* release time.

        The scheduled time is never used: a calendar entry does not prove that a
        value was published.  Raises ``ValueError`` for unreleased events.
        """
        if self.actual_release_at is None:
            raise ValueError(
                f"release {self.release_id!r} has no actual_release_at; a scheduled time "
                "cannot be used as availability"
            )
        return AvailabilityStamp(
            available_at=self.actual_release_at,
            precision=AvailabilityPrecision.EXACT_TIMESTAMP,
            availability_source=AvailabilitySource.OFFICIAL_RELEASE_SCHEDULE,
            raw_available_date=self.actual_release_at_local.date()
            if self.actual_release_at_local is not None
            else None,
            resolver_version=resolver_version,
        )
