"""Explicit U.S. trading calendar (Task 2.14)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from macrosignal.calendar.trading import CalendarRangeError, UsTradingCalendar, holidays

NY = ZoneInfo("America/New_York")
CAL = UsTradingCalendar()


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 4, 3),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
    ],
)
def test_2026_holidays(day: date) -> None:
    assert not CAL.is_session(day)


def test_holiday_count_and_observance_rules() -> None:
    assert len(holidays(2026)) == 10
    assert date(2026, 7, 3) in holidays(2026)  # Sat Jul 4 observed Fri
    assert date(2022, 12, 26) in holidays(2022)  # Sun Christmas observed Mon
    # Saturday New Year's Day (2022-01-01) is not observed on 2021-12-31.
    assert CAL.is_session(date(2021, 12, 31))
    assert date(2021, 6, 18) not in holidays(2021)  # Juneteenth only from 2022
    assert date(2024, 3, 29) in holidays(2024)  # Good Friday 2024


def test_weekends_and_special_closures() -> None:
    assert not CAL.is_session(date(2026, 11, 28))
    assert not CAL.is_session(date(2012, 10, 29))
    assert not CAL.is_session(date(2025, 1, 9))
    assert (
        UsTradingCalendar(extra_closures=[date(2026, 11, 30)]).is_session(date(2026, 11, 30))
        is False
    )


def test_early_closes_and_session_times() -> None:
    assert CAL.is_early_close(date(2026, 11, 27))
    assert CAL.is_early_close(date(2026, 12, 24))
    assert CAL.is_early_close(date(2024, 7, 3))
    assert not CAL.is_early_close(date(2026, 7, 2))
    assert CAL.session_close(date(2026, 11, 27)) == datetime(2026, 11, 27, 13, 0, tzinfo=NY)
    assert CAL.session_close(date(2026, 11, 25)) == datetime(2026, 11, 25, 16, 0, tzinfo=NY)
    assert CAL.session_open(date(2026, 11, 25)) == datetime(2026, 11, 25, 9, 30, tzinfo=NY)
    with pytest.raises(ValueError, match="not a trading session"):
        CAL.session_close(date(2026, 11, 26))


def test_navigation() -> None:
    assert CAL.next_session(date(2026, 11, 25)) == date(2026, 11, 27)
    assert CAL.previous_session(date(2026, 11, 30)) == date(2026, 11, 27)
    assert CAL.sessions(date(2026, 11, 23), date(2026, 11, 30)) == [
        date(2026, 11, 23),
        date(2026, 11, 24),
        date(2026, 11, 25),
        date(2026, 11, 27),
        date(2026, 11, 30),
    ]
    assert len(CAL.sessions(date(2026, 1, 1), date(2026, 12, 31))) == 251


def test_out_of_range_rejected() -> None:
    with pytest.raises(CalendarRangeError):
        CAL.is_session(date(1999, 12, 31))
