"""Macro event-to-market alignment (Task 4.11)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import AvailabilityPrecision, ReleaseEvent, ReleaseStage
from macrosignal.event_study.alignment import (
    EventAlignmentError,
    EventTiming,
    align_event,
    align_timestamp,
)

NY = ZoneInfo("America/New_York")
CAL = UsTradingCalendar()


def _event(at: datetime | None, stage: str = "initial") -> ReleaseEvent:
    sched = at or datetime(2026, 10, 15, 8, 30, tzinfo=NY)
    return ReleaseEvent(
        release_id="CPI-2026-09",
        release_family="CPI",
        release_name="CPI",
        source="bls",
        calendar_snapshot_id="cal",
        source_timezone="America/New_York",
        scheduled_at=sched,
        actual_release_at=at,
        reference_start=date(2026, 9, 1),
        reference_end=date(2026, 9, 30),
        release_stage=stage,
    )


def test_pre_open_release_reacts_same_session() -> None:
    a = align_event(_event(datetime(2026, 10, 15, 8, 30, tzinfo=NY)), CAL)
    assert a.timing is EventTiming.PRE_OPEN
    assert a.reaction_session == date(2026, 10, 15) and a.baseline_session == date(2026, 10, 14)
    assert a.baseline_close == datetime(2026, 10, 14, 16, 0, tzinfo=NY)
    assert a.open_is_post_event and a.release_stage is ReleaseStage.INITIAL
    assert a.precision is AvailabilityPrecision.EXACT_TIMESTAMP


def test_market_hours_and_post_close() -> None:
    fomc = align_event(_event(datetime(2026, 10, 28, 14, 0, tzinfo=NY)), CAL)
    assert fomc.timing is EventTiming.MARKET_HOURS
    assert fomc.reaction_session == date(2026, 10, 28) and not fomc.open_is_post_event
    late = align_event(_event(datetime(2026, 10, 28, 16, 30, tzinfo=NY)), CAL)
    assert late.timing is EventTiming.POST_CLOSE
    assert late.baseline_session == date(2026, 10, 28) and late.reaction_session == date(
        2026, 10, 29
    )


def test_weekend_holiday_and_early_close() -> None:
    sat = align_event(_event(datetime(2026, 10, 17, 10, 0, tzinfo=NY)), CAL)
    assert sat.timing is EventTiming.NON_SESSION
    assert (sat.baseline_session, sat.reaction_session) == (date(2026, 10, 16), date(2026, 10, 19))
    thanksgiving = align_event(_event(datetime(2026, 11, 26, 8, 30, tzinfo=NY)), CAL)
    assert thanksgiving.reaction_session == date(2026, 11, 27)
    after_early_close = align_event(_event(datetime(2026, 11, 27, 13, 30, tzinfo=NY)), CAL)
    assert after_early_close.timing is EventTiming.POST_CLOSE
    assert after_early_close.baseline_close == datetime(2026, 11, 27, 13, 0, tzinfo=NY)


def test_timezone_conversion_uses_new_york_time() -> None:
    a = align_event(_event(datetime(2026, 10, 15, 12, 30, tzinfo=UTC)), CAL)  # 08:30 EDT
    assert a.timing is EventTiming.PRE_OPEN
    b = align_event(_event(datetime(2026, 12, 10, 13, 30, tzinfo=UTC)), CAL)  # 08:30 EST
    assert b.timing is EventTiming.PRE_OPEN and b.event_time_local.hour == 8


def test_date_level_precision_is_conservative() -> None:
    a = align_timestamp(
        release_id="INDPRO-2026-09",
        release_family="ACTIVITY",
        release_stage=None,
        event_time=datetime(2026, 10, 16, 23, 59, 59, tzinfo=NY),
        precision=AvailabilityPrecision.RELEASE_DATE_ONLY,
        calendar=CAL,
    )
    assert a.timing is EventTiming.DATE_LEVEL
    assert a.baseline_session == date(2026, 10, 15)  # before the release date
    assert a.reaction_session == date(2026, 10, 19)  # first session after the date


def test_guards() -> None:
    with pytest.raises(EventAlignmentError, match="no actual release"):
        align_event(_event(None), CAL)
    with pytest.raises(EventAlignmentError, match="unknown"):
        align_event(
            _event(datetime(2026, 10, 15, 8, 30, tzinfo=NY)), CAL, AvailabilityPrecision.UNKNOWN
        )
