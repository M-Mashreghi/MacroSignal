"""Federal Reserve FOMC meeting / statement event calendar.

FOMC statements are *policy events*, not macro data releases: they have no
reference period or release stage, and they never produce a
``MacroObservation``.  Each :class:`FomcMeeting` therefore carries its own
event kind and a statement :class:`~macrosignal.domain.ReleaseEvent` in the
separate ``FOMC_STATEMENT`` family.

Input is a versioned CSV schedule (``meeting_start, meeting_end,
statement_scheduled_at, statement_released_at, unscheduled,
has_projections``) compiled from the official Federal Reserve FOMC calendar.
Statement times must be explicit timezone-aware ISO timestamps: this module
never assumes a time of day.

:func:`policy_surprise` returns ``None`` unless a valid pre-meeting consensus
expectation is supplied; the announced decision on its own is never turned
into a "surprise".
"""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from macrosignal.domain import (
    ConsensusExpectation,
    ReleaseEvent,
    SurpriseMode,
    check_pre_release,
)

FOMC_FAMILY = "FOMC_STATEMENT"
FOMC_TIMEZONE = "America/New_York"
SOURCE = "federal_reserve"
REQUIRED_COLUMNS = (
    "meeting_start",
    "meeting_end",
    "statement_scheduled_at",
    "statement_released_at",
    "unscheduled",
    "has_projections",
)


class FomcScheduleError(ValueError):
    """Malformed or inconsistent FOMC schedule input."""


class PolicyEventKind(StrEnum):
    POLICY_STATEMENT = "policy_statement"


class FomcMeeting(BaseModel):
    """One FOMC meeting and its statement event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_kind: Literal[PolicyEventKind.POLICY_STATEMENT] = PolicyEventKind.POLICY_STATEMENT
    meeting_id: str
    meeting_start: date
    meeting_end: date
    unscheduled: bool
    has_projections: bool
    statement: ReleaseEvent

    @model_validator(mode="after")
    def _check(self) -> FomcMeeting:
        problems: list[str] = []
        if self.meeting_end < self.meeting_start:
            problems.append("meeting_end is before meeting_start")
        if (self.meeting_end - self.meeting_start).days > 2:
            problems.append("an FOMC meeting spans at most three calendar days")
        s = self.statement
        if s.release_family != FOMC_FAMILY:
            problems.append(f"statement must be in the {FOMC_FAMILY} family")
        if s.reference_start is not None or s.release_stage is not None:
            problems.append("FOMC statements have no reference period or release stage")
        if s.scheduled_at_local.date() != self.meeting_end:
            problems.append("the statement is scheduled on the last meeting day")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def statement_time(self) -> datetime | None:
        """When the statement was actually released (None until recorded)."""
        return self.statement.actual_release_at


class FomcCalendarSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    calendar_snapshot_id: str
    retrieved_at: AwareDatetime
    meetings: tuple[FomcMeeting, ...]

    def statement_events(self) -> list[ReleaseEvent]:
        return [m.statement for m in self.meetings]

    def meeting_on(self, day: date) -> FomcMeeting | None:
        for m in self.meetings:
            if m.meeting_start <= day <= m.meeting_end:
                return m
        return None


def _bool(value: str, column: str) -> bool:
    v = value.strip().lower()
    if v in ("true", "1", "yes"):
        return True
    if v in ("false", "0", "no"):
        return False
    raise FomcScheduleError(f"{column}: expected true/false, got {value!r}")


def _aware(value: str, column: str) -> datetime:
    try:
        ts = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise FomcScheduleError(f"{column}: {value!r} is not an ISO timestamp") from exc
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise FomcScheduleError(f"{column}: {value!r} has no timezone; times are never assumed")
    return ts


def parse_fomc_schedule(
    text: str, *, retrieved_at: datetime, calendar_snapshot_id: str | None = None
) -> FomcCalendarSnapshot:
    snapshot_id = calendar_snapshot_id or (
        "cal_fomc_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
    )
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise FomcScheduleError(f"FOMC schedule is missing columns {missing}")
    meetings: list[FomcMeeting] = []
    for line, row in enumerate(reader, start=2):
        try:
            start = date.fromisoformat(row["meeting_start"].strip())
            end = date.fromisoformat(row["meeting_end"].strip())
        except ValueError as exc:
            raise FomcScheduleError(f"line {line}: bad meeting date") from exc
        scheduled = _aware(row["statement_scheduled_at"], "statement_scheduled_at")
        released_raw = row["statement_released_at"].strip()
        released = _aware(released_raw, "statement_released_at") if released_raw else None
        if released is not None and released > retrieved_at:
            raise FomcScheduleError(f"line {line}: release recorded after the snapshot time")
        meeting_id = f"FOMC-{end.isoformat()}"
        try:
            statement = ReleaseEvent(
                release_id=meeting_id,
                release_family=FOMC_FAMILY,
                release_name="FOMC Statement",
                source=SOURCE,
                calendar_snapshot_id=snapshot_id,
                source_timezone=FOMC_TIMEZONE,
                scheduled_at=scheduled,
                actual_release_at=released,
            )
            meetings.append(
                FomcMeeting(
                    meeting_id=meeting_id,
                    meeting_start=start,
                    meeting_end=end,
                    unscheduled=_bool(row["unscheduled"], "unscheduled"),
                    has_projections=_bool(row["has_projections"], "has_projections"),
                    statement=statement,
                )
            )
        except ValueError as exc:
            raise FomcScheduleError(f"line {line}: {exc}") from exc
    meetings.sort(key=lambda m: m.meeting_start)
    for a, b in zip(meetings, meetings[1:], strict=False):
        if b.meeting_start <= a.meeting_end:
            raise FomcScheduleError(f"overlapping meetings {a.meeting_id} and {b.meeting_id}")
    return FomcCalendarSnapshot(
        calendar_snapshot_id=snapshot_id, retrieved_at=retrieved_at, meetings=tuple(meetings)
    )


class PolicySurprise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    meeting_id: str
    decided_value: float
    expected_value: float
    surprise: float
    expectation_source: str
    units: str


def policy_surprise(
    meeting: FomcMeeting,
    decided_value: float,
    expectation: ConsensusExpectation | None,
    *,
    max_expectation_age: timedelta | None = None,
) -> PolicySurprise | None:
    """Decision minus a valid pre-meeting consensus; ``None`` without one.

    The expectation must be a consensus (not a model forecast), keyed to this
    meeting's ``meeting_id``, and available strictly before the statement's
    actual release (``check_pre_release``).  ``max_expectation_age`` optionally
    rejects stale expectations.
    """
    if expectation is None:
        return None
    if expectation.release_id != meeting.meeting_id:
        raise ValueError(f"expectation is for {expectation.release_id}, not {meeting.meeting_id}")
    release_at = meeting.statement.actual_release_at
    if release_at is None:
        raise ValueError(f"{meeting.meeting_id} has no recorded statement release time")
    check_pre_release(expectation, release_at, SurpriseMode.MARKET_SURPRISE)
    if max_expectation_age is not None:
        if release_at - expectation.availability.available_at > max_expectation_age:
            raise ValueError("pre-meeting expectation is older than max_expectation_age")
    return PolicySurprise(
        meeting_id=meeting.meeting_id,
        decided_value=decided_value,
        expected_value=expectation.expected_value,
        surprise=decided_value - expectation.expected_value,
        expectation_source=expectation.expectation_source,
        units=expectation.units,
    )
