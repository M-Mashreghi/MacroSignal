"""BEA release schedule adapter with GDP estimate stages and PCE releases.

BEA's release schedule lists each release with a title, date and Eastern Time
release time.  This adapter turns schedule entries into
:class:`~macrosignal.domain.ReleaseEvent`s, keeping every GDP estimate round as
its own event:

* ``GDP`` (quarterly reference period): ``advance``, ``second`` and ``third``
  estimates are separate stages; annual/comprehensive updates are
  ``benchmark_revision``.  Titles such as ``GDP (Advance Estimate), 3rd Quarter
  2026`` or ``Gross Domestic Product, Third Quarter 2026 (Second Estimate)`` are
  recognised.
* ``PCE`` (monthly reference period): ``Personal Income and Outlays, <Month>
  <Year>`` is the initial release of that month's PCE data.

A combined title (GDP estimate *and* Personal Income and Outlays) yields one
event per family at the same time.  Unrecognised titles are skipped and listed.
Stages of the same quarter must be scheduled in order (advance < second <
third) and a (family, period, stage) may appear only once, so revisions are
never collapsed or reordered.

Input can be an iCalendar feed (:func:`parse_bea_ics`) or already-extracted
``(title, timestamp)`` rows (:func:`parse_bea_schedule_rows`).  No feed URL is
hard-coded: callers pass the official schedule URL they have verified.
"""

from __future__ import annotations

import calendar as _calendar
import re
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict

from macrosignal.calendar.ics import IcsParseError, parse_datetime, parse_events
from macrosignal.data.http import HttpClient
from macrosignal.domain import ReleaseEvent, ReleaseStage

BEA_TIMEZONE = "America/New_York"
BEA_TZ_ALIASES = {
    "US-Eastern": BEA_TIMEZONE,
    "US/Eastern": BEA_TIMEZONE,
    "America/New_York": BEA_TIMEZONE,
    "Eastern Standard Time": BEA_TIMEZONE,
}
SOURCE = "bea"

_MONTHS = {name.lower(): i for i, name in enumerate(_calendar.month_name) if name}
_QUARTER_WORDS = {
    "1st": 1,
    "first": 1,
    "2nd": 2,
    "second": 2,
    "3rd": 3,
    "third": 3,
    "4th": 4,
    "fourth": 4,
}
_GDP = re.compile(r"\b(GDP|Gross Domestic Product)\b", re.I)
_QUARTER = re.compile(
    r"\b(1st|2nd|3rd|4th|First|Second|Third|Fourth) Quarter(?: and Year)? (\d{4})\b", re.I
)
_STAGE = re.compile(r"\b(Advance|Second|Third) Estimate\b", re.I)
_UPDATE = re.compile(r"\b(Annual|Comprehensive) Update\b", re.I)
_MONTH_NAMES = "|".join(m for m in _calendar.month_name if m)
_PIO = re.compile(rf"\bPersonal Income and Outlays\b.*?\b({_MONTH_NAMES}) (\d{{4}})\b", re.I)

_STAGE_WORDS = {
    "advance": ReleaseStage.ADVANCE,
    "second": ReleaseStage.SECOND,
    "third": ReleaseStage.THIRD,
}
GDP_STAGE_ORDER = (ReleaseStage.ADVANCE, ReleaseStage.SECOND, ReleaseStage.THIRD)


class BeaScheduleError(ValueError):
    """Inconsistent BEA schedule content."""


class BeaCalendarSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    calendar_snapshot_id: str
    retrieved_at: AwareDatetime
    events: tuple[ReleaseEvent, ...]
    skipped_titles: tuple[str, ...]

    def for_family(self, family: str) -> list[ReleaseEvent]:
        return [e for e in self.events if e.release_family == family]

    def gdp_stages(self, year: int, quarter: int) -> dict[ReleaseStage, ReleaseEvent]:
        start = date(year, 3 * quarter - 2, 1)
        return {
            e.release_stage: e
            for e in self.for_family("GDP")
            if e.reference_start == start and e.release_stage is not None
        }


def _quarter_period(year: int, quarter: int) -> tuple[date, date]:
    first = 3 * quarter - 2
    return date(year, first, 1), date(year, first + 2, _calendar.monthrange(year, first + 2)[1])


def classify_title(title: str) -> list[tuple[str, date, date, ReleaseStage, str]]:
    """(family, reference_start, reference_end, stage, release_id) for each release in a title."""
    out: list[tuple[str, date, date, ReleaseStage, str]] = []
    if _GDP.search(title):
        q = _QUARTER.search(title)
        stage_m = _STAGE.search(title)
        update_m = _UPDATE.search(title)
        if q and (stage_m or update_m):
            quarter = _QUARTER_WORDS[q.group(1).lower()]
            year = int(q.group(2))
            stage = (
                _STAGE_WORDS[stage_m.group(1).lower()]
                if stage_m
                else ReleaseStage.BENCHMARK_REVISION
            )
            start, end = _quarter_period(year, quarter)
            out.append(("GDP", start, end, stage, f"GDP-{year}Q{quarter}-{stage.value}"))
    pio = _PIO.search(title)
    if pio:
        month = _MONTHS.get(pio.group(1).lower())
        if month is not None:
            year = int(pio.group(2))
            end = date(year, month, _calendar.monthrange(year, month)[1])
            out.append(
                ("PCE", date(year, month, 1), end, ReleaseStage.INITIAL, f"PCE-{year}-{month:02d}")
            )
    return out


def parse_bea_schedule_rows(
    rows: Iterable[tuple[str, datetime]],
    *,
    calendar_snapshot_id: str,
    retrieved_at: datetime,
    confirm_past_events: bool = False,
    confirmation_lag: timedelta = timedelta(days=1),
) -> BeaCalendarSnapshot:
    events: dict[str, ReleaseEvent] = {}
    skipped: list[str] = []
    for title, when in rows:
        if when.tzinfo is None or when.utcoffset() is None:
            raise BeaScheduleError(f"{title}: release time must be timezone-aware")
        classified = classify_title(title)
        if not classified:
            skipped.append(title)
            continue
        actual = when if confirm_past_events and when + confirmation_lag <= retrieved_at else None
        for family, start, end, stage, release_id in classified:
            event = ReleaseEvent(
                release_id=release_id,
                release_family=family,
                release_name=title,
                source=SOURCE,
                calendar_snapshot_id=calendar_snapshot_id,
                source_timezone=BEA_TIMEZONE,
                scheduled_at=when,
                actual_release_at=actual,
                reference_start=start,
                reference_end=end,
                release_stage=stage,
            )
            if release_id in events and events[release_id] != event:
                raise BeaScheduleError(f"conflicting schedule entries for {release_id}")
            events[release_id] = event
    _check_stage_order(events.values())
    ordered = tuple(sorted(events.values(), key=lambda e: (e.scheduled_at, e.release_id)))
    return BeaCalendarSnapshot(
        calendar_snapshot_id=calendar_snapshot_id,
        retrieved_at=retrieved_at,
        events=ordered,
        skipped_titles=tuple(sorted(set(skipped))),
    )


def _check_stage_order(events: Iterable[ReleaseEvent]) -> None:
    by_quarter: dict[date, dict[ReleaseStage, datetime]] = {}
    for e in events:
        if e.release_family == "GDP" and e.release_stage in GDP_STAGE_ORDER:
            assert e.reference_start is not None and e.release_stage is not None
            by_quarter.setdefault(e.reference_start, {})[e.release_stage] = e.scheduled_at
    for quarter, stages in by_quarter.items():
        times = [stages[s] for s in GDP_STAGE_ORDER if s in stages]
        if times != sorted(times) or len(set(times)) != len(times):
            raise BeaScheduleError(
                f"GDP estimate stages for {quarter} are not in chronological order"
            )


def parse_bea_ics(
    text: str, *, calendar_snapshot_id: str, retrieved_at: datetime, **kwargs: object
) -> BeaCalendarSnapshot:
    rows: list[tuple[str, datetime]] = []
    for ev in parse_events(text):
        title = ev.text("SUMMARY")
        start = ev.get("DTSTART")
        if not title or start is None:
            raise IcsParseError("VEVENT without SUMMARY or DTSTART")
        when = parse_datetime(start, BEA_TZ_ALIASES, BEA_TIMEZONE)
        if not isinstance(when, datetime):
            if classify_title(title):
                raise IcsParseError(f"{title}: schedule entry has a date but no release time")
            continue
        rows.append((title, when))
    return parse_bea_schedule_rows(
        rows,
        calendar_snapshot_id=calendar_snapshot_id,
        retrieved_at=retrieved_at,
        **kwargs,  # type: ignore[arg-type]
    )


def fetch_bea_calendar(http: HttpClient, url: str, **kwargs: object) -> BeaCalendarSnapshot:
    """Fetch an iCalendar schedule from a caller-verified official BEA URL."""
    response = http.get(url)
    return parse_bea_ics(
        response.content.decode("utf-8"),
        calendar_snapshot_id=response.snapshot.snapshot_id,
        retrieved_at=response.snapshot.retrieved_at,
        **kwargs,
    )
