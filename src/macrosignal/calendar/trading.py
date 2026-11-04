"""Explicit U.S. equity (NYSE) trading calendar.

Rule-based for 2000-2099: weekends, the standard NYSE full-day holidays with
weekend observance, a documented list of special (unscheduled) closures, and
the standard 13:00 ET early closes.  Dates outside the supported range raise
rather than guessing.  This is a *market* calendar; macro release calendars
are separate objects (``docs/RETURN_AND_EXECUTION_CONTRACT.md``).

Holidays: New Year's Day, Martin Luther King Jr. Day, Washington's Birthday,
Good Friday, Memorial Day, Juneteenth (from 2022), Independence Day, Labor Day,
Thanksgiving, Christmas.  Saturday holidays are observed the preceding Friday
and Sunday holidays the following Monday, except that New Year's Day falling on
a Saturday is not observed on the preceding December 31.

Early closes (13:00 ET): July 3 when it is a weekday session before a weekday
Independence Day, the day after Thanksgiving, and December 24 when it is a
weekday session.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from functools import cache
from zoneinfo import ZoneInfo

NYSE_TIMEZONE = ZoneInfo("America/New_York")
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)
FIRST_YEAR = 2000
LAST_YEAR = 2099

#: Unscheduled full-day market closures (documented events).
SPECIAL_CLOSURES: frozenset[date] = frozenset(
    {
        date(2001, 9, 11),
        date(2001, 9, 12),
        date(2001, 9, 13),
        date(2001, 9, 14),  # September 11 attacks
        date(2004, 6, 11),  # National day of mourning, President Reagan
        date(2007, 1, 2),  # National day of mourning, President Ford
        date(2012, 10, 29),
        date(2012, 10, 30),  # Hurricane Sandy
        date(2018, 12, 5),  # National day of mourning, President G.H.W. Bush
        date(2025, 1, 9),  # National day of mourning, President Carter
    }
)


class CalendarRangeError(ValueError):
    """Date outside the calendar's supported range."""


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month = (h + ll - 7 * m + 114) // 31
    day = (h + ll - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _observed(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


@cache
def holidays(year: int) -> frozenset[date]:
    """NYSE full-day holidays observed in ``year``."""
    _check_year(year)
    days: set[date] = set()
    new_year = date(year, 1, 1)
    if new_year.weekday() != 5:  # Saturday New Year's Day is not observed
        days.add(_observed(new_year))
    days.add(_nth_weekday(year, 1, 0, 3))  # MLK Day
    days.add(_nth_weekday(year, 2, 0, 3))  # Washington's Birthday
    days.add(_easter(year) - timedelta(days=2))  # Good Friday
    days.add(_last_weekday(year, 5, 0))  # Memorial Day
    if year >= 2022:
        days.add(_observed(date(year, 6, 19)))  # Juneteenth
    days.add(_observed(date(year, 7, 4)))
    days.add(_nth_weekday(year, 9, 0, 1))  # Labor Day
    days.add(_nth_weekday(year, 11, 3, 4))  # Thanksgiving
    days.add(_observed(date(year, 12, 25)))
    return frozenset(d for d in days if d.year == year)


def _check_year(year: int) -> None:
    if not FIRST_YEAR <= year <= LAST_YEAR:
        raise CalendarRangeError(f"trading calendar supports {FIRST_YEAR}-{LAST_YEAR}, got {year}")


class UsTradingCalendar:
    """NYSE sessions, holidays, early closes and session timestamps."""

    name = "nyse"
    timezone = NYSE_TIMEZONE

    def __init__(self, extra_closures: Iterable[date] = ()) -> None:
        self.closures = SPECIAL_CLOSURES | frozenset(extra_closures)

    def is_session(self, day: date) -> bool:
        _check_year(day.year)
        return day.weekday() < 5 and day not in holidays(day.year) and day not in self.closures

    def is_early_close(self, day: date) -> bool:
        if not self.is_session(day):
            return False
        if day.month == 7 and day.day == 3:
            july4 = date(day.year, 7, 4)
            return july4.weekday() < 5
        if day.month == 11 and day == _nth_weekday(day.year, 11, 3, 4) + timedelta(days=1):
            return True
        return day.month == 12 and day.day == 24

    def session_open(self, day: date) -> datetime:
        if not self.is_session(day):
            raise ValueError(f"{day} is not a trading session")
        return datetime.combine(day, REGULAR_OPEN, tzinfo=NYSE_TIMEZONE)

    def session_close(self, day: date) -> datetime:
        if not self.is_session(day):
            raise ValueError(f"{day} is not a trading session")
        close = EARLY_CLOSE if self.is_early_close(day) else REGULAR_CLOSE
        return datetime.combine(day, close, tzinfo=NYSE_TIMEZONE)

    def sessions(self, start: date, end: date) -> list[date]:
        out: list[date] = []
        d = start
        while d <= end:
            if self.is_session(d):
                out.append(d)
            d += timedelta(days=1)
        return out

    def next_session(self, day: date) -> date:
        d = day + timedelta(days=1)
        while not self.is_session(d):
            d += timedelta(days=1)
        return d

    def previous_session(self, day: date) -> date:
        d = day - timedelta(days=1)
        while not self.is_session(d):
            d -= timedelta(days=1)
        return d
