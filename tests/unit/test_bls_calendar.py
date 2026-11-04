"""BLS release calendar adapter (Task 2.7)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from macrosignal.calendar.bls import (
    diff_calendars,
    fetch_bls_calendar,
    parse_bls_calendar,
    text_snapshot_id,
)
from macrosignal.calendar.ics import IcsParseError
from macrosignal.data.http import HttpClient
from macrosignal.domain import ReleaseStage

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "bls"
NY = ZoneInfo("America/New_York")
RETRIEVED = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _text(name: str = "schedule_v1.ics") -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _parse(text: str | None = None, **kw: object):  # type: ignore[no-untyped-def]
    body = text if text is not None else _text()
    return parse_bls_calendar(
        body,
        calendar_snapshot_id=text_snapshot_id(body),
        retrieved_at=RETRIEVED,
        **kw,  # type: ignore[arg-type]
    )


def test_parses_supported_families_with_eastern_time() -> None:
    snap = _parse()
    ids = [e.release_id for e in snap.events]
    assert ids == [
        "CPI-2026-08",
        "EMPLOYMENT_SITUATION-2026-09",
        "CPI-2026-09",
        "ECI-2026Q3",
        "CPI-2026-11",
    ]
    cpi = snap.for_family("CPI")[1]
    assert cpi.scheduled_at == datetime(2026, 10, 15, 8, 30, tzinfo=NY)
    assert cpi.scheduled_at_utc == datetime(2026, 10, 15, 12, 30, tzinfo=UTC)
    assert cpi.reference_start == date(2026, 9, 1) and cpi.reference_end == date(2026, 9, 30)
    assert cpi.release_stage is ReleaseStage.INITIAL
    assert cpi.source_timezone == "America/New_York"
    eci = snap.for_family("ECI")[0]
    assert (eci.reference_start, eci.reference_end) == (date(2026, 7, 1), date(2026, 9, 30))
    assert snap.skipped_titles == ("State Employment and Unemployment for September 2026",)


def test_dst_transition_respected() -> None:
    nov = _parse().for_family("CPI")[-1]  # 10 Dec 2026 is EST
    assert nov.scheduled_at_utc.hour == 13


def test_schedule_is_not_proof_of_release() -> None:
    assert all(e.actual_release_at is None for e in _parse().events)
    with pytest.raises(ValueError, match="scheduled time cannot be used"):
        _parse().events[0].to_availability_stamp(resolver_version="x")


def test_opt_in_confirmation_of_past_events() -> None:
    snap = _parse(confirm_past_events=True, confirmation_lag=timedelta(days=1))
    released = {e.release_id: e.actual_release_at for e in snap.events}
    assert released["CPI-2026-09"] == datetime(2026, 10, 15, 8, 30, tzinfo=NY)
    assert released["CPI-2026-11"] is None  # still in the future at retrieval
    # ECI on 31 Oct is > 1 day before 4 Nov retrieval -> confirmed.
    assert released["ECI-2026Q3"] is not None


def test_snapshot_ids_and_rescheduling_diff() -> None:
    v1 = _parse(_text("schedule_v1.ics"))
    v2 = _parse(_text("schedule_v2.ics"))
    assert v1.calendar_snapshot_id != v2.calendar_snapshot_id
    assert all(e.calendar_snapshot_id == v1.calendar_snapshot_id for e in v1.events)
    changes = diff_calendars(v1, v2)
    assert [(c.release_id, c.change) for c in changes] == [("CPI-2026-11", "rescheduled")]
    assert changes[0].current == datetime(2026, 12, 11, 8, 30, tzinfo=NY)
    trimmed = v2.model_copy(update={"events": v2.events[:-1]})
    assert [(c.release_id, c.change) for c in diff_calendars(v1, trimmed)] == [
        ("CPI-2026-11", "removed")
    ]


def test_family_filter() -> None:
    snap = _parse(families=("CPI",))
    assert {e.release_family for e in snap.events} == {"CPI"}


@pytest.mark.parametrize(
    ("dtstart", "match"),
    [
        ("DTSTART;VALUE=DATE:20261015", "no release time"),
        ("DTSTART;TZID=Europe/Paris:20261015T083000", "unsupported TZID"),
        ("DTSTART;TZID=US-Eastern:2026-10-15", "bad DATE-TIME"),
    ],
)
def test_bad_times_rejected(dtstart: str, match: str) -> None:
    text = _text().replace("DTSTART;TZID=US-Eastern:20261015T083000", dtstart)
    with pytest.raises(IcsParseError, match=match):
        _parse(text)


def test_floating_time_uses_documented_eastern_and_utc_suffix() -> None:
    text = _text().replace("DTSTART;TZID=US-Eastern:20261015T083000", "DTSTART:20261015T083000")
    assert _parse(text).for_family("CPI")[1].scheduled_at == datetime(
        2026, 10, 15, 8, 30, tzinfo=NY
    )
    text = _text().replace("DTSTART;TZID=US-Eastern:20261015T083000", "DTSTART:20261015T123000Z")
    assert _parse(text).for_family("CPI")[1].scheduled_at_utc == datetime(
        2026, 10, 15, 12, 30, tzinfo=UTC
    )


def test_conflicting_duplicate_entries_rejected() -> None:
    dup = _text().replace(
        "END:VCALENDAR",
        "BEGIN:VEVENT\nDTSTART;TZID=US-Eastern:20261016T083000\n"
        "SUMMARY:Consumer Price Index for September 2026\nEND:VEVENT\nEND:VCALENDAR",
    )
    with pytest.raises(IcsParseError, match="conflicting"):
        _parse(dup)


def test_unterminated_event_rejected() -> None:
    with pytest.raises(IcsParseError, match="unterminated"):
        _parse("BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:x\n")


def test_fetch_through_http_client() -> None:
    body = _text().encode("utf-8")
    http = HttpClient(
        "bls",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)),
        sleep=lambda s: None,
        clock=lambda: RETRIEVED,
    )
    snap = fetch_bls_calendar(http)
    assert snap.calendar_snapshot_id.startswith("raw_bls_")
    assert len(snap.events) == 5
