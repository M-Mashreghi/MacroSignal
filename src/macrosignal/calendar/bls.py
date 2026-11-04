"""BLS release calendar adapter (iCalendar schedule -> ReleaseEvent).

BLS publishes its news-release schedule as an iCalendar feed whose times are
U.S. Eastern Time.  This adapter parses that feed into a
:class:`BlsCalendarSnapshot` of :class:`~macrosignal.domain.ReleaseEvent`s for
the supported release families:

=====================  ======================================  ===========
family                 BLS release title                        reference
=====================  ======================================  ===========
CPI                    Consumer Price Index for <Month> <Year>  month
EMPLOYMENT_SITUATION   The Employment Situation for <Month> ..  month
PPI                    Producer Price Index for <Month> <Year>  month
ECI                    Employment Cost Index for <Quarter> ...  quarter
=====================  ======================================  ===========

Unrecognised titles are skipped and listed, never guessed.  Every event cites
the calendar snapshot id (the raw snapshot of the feed) because schedules
change; :func:`diff_calendars` reports rescheduled, added and removed events
between two snapshots.

Scheduled vs actual: a schedule is not proof of publication, so
``actual_release_at`` is left empty unless the caller opts in to
``confirm_past_events``: an event whose scheduled time is at least
``confirmation_lag`` before the snapshot's retrieval time (and is still on the
calendar) is then recorded as released at its scheduled time.  That rule is
documented and switchable; it is the only inference this adapter makes.
"""

from __future__ import annotations

import calendar as _calendar
import hashlib
import re
from datetime import date, datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict

from macrosignal.calendar.ics import IcsParseError, parse_datetime, parse_events
from macrosignal.data.http import HttpClient
from macrosignal.domain import ReleaseEvent, ReleaseStage

BLS_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BLS_TIMEZONE = "America/New_York"
BLS_TZ_ALIASES = {
    "US-Eastern": BLS_TIMEZONE,
    "US/Eastern": BLS_TIMEZONE,
    "America/New_York": BLS_TIMEZONE,
    "Eastern Standard Time": BLS_TIMEZONE,
}
SOURCE = "bls"

_MONTHS = {name.lower(): i for i, name in enumerate(_calendar.month_name) if name}
_QUARTERS = {"first": 1, "second": 2, "third": 3, "fourth": 4}

_MONTHLY_TITLES: dict[str, re.Pattern[str]] = {
    "CPI": re.compile(r"^Consumer Price Index for (\w+) (\d{4})$", re.I),
    "EMPLOYMENT_SITUATION": re.compile(r"^(?:The )?Employment Situation for (\w+) (\d{4})$", re.I),
    "PPI": re.compile(r"^Producer Price Index for (\w+) (\d{4})$", re.I),
}
_ECI_TITLE = re.compile(r"^Employment Cost Index for (\w+) Quarter (\d{4})$", re.I)
SUPPORTED_FAMILIES = (*_MONTHLY_TITLES, "ECI")


class BlsCalendarSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    calendar_snapshot_id: str
    retrieved_at: AwareDatetime
    events: tuple[ReleaseEvent, ...]
    skipped_titles: tuple[str, ...]

    def for_family(self, family: str) -> list[ReleaseEvent]:
        return [e for e in self.events if e.release_family == family]


def _classify(title: str) -> tuple[str, date, date, str] | None:
    """Return (family, reference_start, reference_end, release_id) for a known title."""
    for family, pattern in _MONTHLY_TITLES.items():
        m = pattern.match(title)
        if m:
            month = _MONTHS.get(m.group(1).lower())
            if month is None:
                return None
            year = int(m.group(2))
            end = date(year, month, _calendar.monthrange(year, month)[1])
            return family, date(year, month, 1), end, f"{family}-{year}-{month:02d}"
    m = _ECI_TITLE.match(title)
    if m:
        q = _QUARTERS.get(m.group(1).lower())
        if q is None:
            return None
        year = int(m.group(2))
        first = 3 * q - 2
        end = date(year, first + 2, _calendar.monthrange(year, first + 2)[1])
        return "ECI", date(year, first, 1), end, f"ECI-{year}Q{q}"
    return None


def parse_bls_calendar(
    text: str,
    *,
    calendar_snapshot_id: str,
    retrieved_at: datetime,
    families: tuple[str, ...] = SUPPORTED_FAMILIES,
    confirm_past_events: bool = False,
    confirmation_lag: timedelta = timedelta(days=1),
) -> BlsCalendarSnapshot:
    events: dict[str, ReleaseEvent] = {}
    skipped: list[str] = []
    for ev in parse_events(text):
        title = ev.text("SUMMARY")
        start = ev.get("DTSTART")
        if not title or start is None:
            raise IcsParseError("VEVENT without SUMMARY or DTSTART")
        classified = _classify(title)
        if classified is None or classified[0] not in families:
            skipped.append(title)
            continue
        family, ref_start, ref_end, release_id = classified
        when = parse_datetime(start, BLS_TZ_ALIASES, BLS_TIMEZONE)
        if not isinstance(when, datetime):
            raise IcsParseError(f"{title}: schedule entry has a date but no release time")
        actual = None
        if confirm_past_events and when + confirmation_lag <= retrieved_at:
            actual = when
        event = ReleaseEvent(
            release_id=release_id,
            release_family=family,
            release_name=title,
            source=SOURCE,
            calendar_snapshot_id=calendar_snapshot_id,
            source_timezone=BLS_TIMEZONE,
            scheduled_at=when,
            actual_release_at=actual,
            reference_start=ref_start,
            reference_end=ref_end,
            release_stage=ReleaseStage.INITIAL,
        )
        if release_id in events and events[release_id] != event:
            raise IcsParseError(f"conflicting schedule entries for {release_id}")
        events[release_id] = event
    ordered = tuple(sorted(events.values(), key=lambda e: (e.scheduled_at, e.release_id)))
    return BlsCalendarSnapshot(
        calendar_snapshot_id=calendar_snapshot_id,
        retrieved_at=retrieved_at,
        events=ordered,
        skipped_titles=tuple(sorted(set(skipped))),
    )


def text_snapshot_id(text: str) -> str:
    """Content-derived calendar snapshot id for feeds not fetched through HttpClient."""
    return "cal_bls_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def fetch_bls_calendar(
    http: HttpClient, *, url: str = BLS_SCHEDULE_URL, **kwargs: object
) -> BlsCalendarSnapshot:
    response = http.get(url)
    try:
        text = response.content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IcsParseError("BLS schedule is not UTF-8 text") from exc
    return parse_bls_calendar(
        text,
        calendar_snapshot_id=response.snapshot.snapshot_id,
        retrieved_at=response.snapshot.retrieved_at,
        **kwargs,  # type: ignore[arg-type]
    )


class CalendarChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    change: str  # "added" | "removed" | "rescheduled"
    previous: AwareDatetime | None
    current: AwareDatetime | None


def diff_calendars(old: BlsCalendarSnapshot, new: BlsCalendarSnapshot) -> list[CalendarChange]:
    """Schedule changes between two snapshots (both are kept; nothing is overwritten)."""
    before = {e.release_id: e.scheduled_at for e in old.events}
    after = {e.release_id: e.scheduled_at for e in new.events}
    changes: list[CalendarChange] = []
    for rid in sorted(before.keys() | after.keys()):
        b, a = before.get(rid), after.get(rid)
        if b is None:
            changes.append(CalendarChange(release_id=rid, change="added", previous=None, current=a))
        elif a is None:
            changes.append(
                CalendarChange(release_id=rid, change="removed", previous=b, current=None)
            )
        elif a != b:
            changes.append(
                CalendarChange(release_id=rid, change="rescheduled", previous=b, current=a)
            )
    return changes
