"""Macro event-to-market session alignment.

Maps a release (its *actual* time, timezone and precision) onto the U.S.
trading calendar:

=================  ====================================  ==========================
timing             condition (America/New_York)          first reacting session
=================  ====================================  ==========================
pre_open           session day, before 09:30             same session (open)
market_hours       session day, 09:30 <= t < close       same session (close only)
post_close         session day, at/after the close       next session
non_session        weekend / holiday / closure           next session
date_level         precision is date-only / inferred     next session after the date
=================  ====================================  ==========================

The **baseline** is the close of the last session strictly before the
information could be known (for date-level precision: before the event date),
so a pre-event price never contains the release.  Event-time precision and
release stage are preserved; for ``market_hours`` events the same-session open
is *before* the event and is flagged as not a clean pre/post pair.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import AvailabilityPrecision, ReleaseEvent, ReleaseStage

EXACT_PRECISIONS = frozenset(
    {AvailabilityPrecision.EXACT_TIMESTAMP, AvailabilityPrecision.PROVIDER_TIMESTAMP}
)


class EventTiming(StrEnum):
    PRE_OPEN = "pre_open"
    MARKET_HOURS = "market_hours"
    POST_CLOSE = "post_close"
    NON_SESSION = "non_session"
    DATE_LEVEL = "date_level"


class EventMarketAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    release_family: str
    release_stage: ReleaseStage | None
    event_time: AwareDatetime
    event_time_local: AwareDatetime
    precision: AvailabilityPrecision
    timing: EventTiming
    baseline_session: date
    baseline_close: AwareDatetime
    reaction_session: date
    reaction_open: AwareDatetime
    reaction_close: AwareDatetime
    open_is_post_event: bool


class EventAlignmentError(ValueError):
    """The event cannot be aligned (no actual time, or unknown precision)."""


def align_timestamp(
    *,
    release_id: str,
    release_family: str,
    release_stage: ReleaseStage | None,
    event_time: datetime,
    precision: AvailabilityPrecision,
    calendar: UsTradingCalendar,
) -> EventMarketAlignment:
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise EventAlignmentError("event time must be timezone-aware")
    if precision is AvailabilityPrecision.UNKNOWN:
        raise EventAlignmentError(f"{release_id}: unknown event-time precision cannot be aligned")
    local = event_time.astimezone(calendar.timezone)
    day = local.date()
    if precision not in EXACT_PRECISIONS:
        timing = EventTiming.DATE_LEVEL
        reaction = calendar.next_session(day)
        baseline = calendar.previous_session(day)
    elif not calendar.is_session(day):
        timing = EventTiming.NON_SESSION
        reaction = calendar.next_session(day)
        baseline = calendar.previous_session(day)
    elif local < calendar.session_open(day):
        timing, reaction, baseline = EventTiming.PRE_OPEN, day, calendar.previous_session(day)
    elif local < calendar.session_close(day):
        timing, reaction, baseline = EventTiming.MARKET_HOURS, day, calendar.previous_session(day)
    else:
        timing = EventTiming.POST_CLOSE
        reaction = calendar.next_session(day)
        baseline = day
    reaction_open = calendar.session_open(reaction)
    return EventMarketAlignment(
        release_id=release_id,
        release_family=release_family,
        release_stage=release_stage,
        event_time=event_time,
        event_time_local=local,
        precision=precision,
        timing=timing,
        baseline_session=baseline,
        baseline_close=calendar.session_close(baseline),
        reaction_session=reaction,
        reaction_open=reaction_open,
        reaction_close=calendar.session_close(reaction),
        open_is_post_event=reaction_open > event_time
        if timing is not EventTiming.DATE_LEVEL
        else True,
    )


def align_event(
    event: ReleaseEvent,
    calendar: UsTradingCalendar,
    precision: AvailabilityPrecision = AvailabilityPrecision.EXACT_TIMESTAMP,
) -> EventMarketAlignment:
    if event.actual_release_at is None:
        raise EventAlignmentError(f"{event.release_id}: no actual release time; cannot align")
    return align_timestamp(
        release_id=event.release_id,
        release_family=event.release_family,
        release_stage=event.release_stage,
        event_time=event.actual_release_at,
        precision=precision,
        calendar=calendar,
    )
