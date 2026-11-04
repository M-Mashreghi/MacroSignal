"""BEA release schedule and estimate stages (Task 2.8)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from macrosignal.calendar.bea import (
    BeaScheduleError,
    classify_title,
    fetch_bea_calendar,
    parse_bea_ics,
    parse_bea_schedule_rows,
)
from macrosignal.data.http import HttpClient
from macrosignal.domain import ReleaseStage

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "bea"
NY = ZoneInfo("America/New_York")
RETRIEVED = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _snap(**kw: object):  # type: ignore[no-untyped-def]
    return parse_bea_ics(
        (FIX / "schedule.ics").read_text(encoding="utf-8"),
        calendar_snapshot_id="cal_bea_fixture",
        retrieved_at=RETRIEVED,
        **kw,
    )


def test_gdp_stages_are_separate_events() -> None:
    stages = _snap().gdp_stages(2026, 2)
    assert set(stages) == {ReleaseStage.ADVANCE, ReleaseStage.SECOND, ReleaseStage.THIRD}
    assert stages[ReleaseStage.ADVANCE].scheduled_at == datetime(2026, 7, 30, 8, 30, tzinfo=NY)
    assert stages[ReleaseStage.THIRD].release_id == "GDP-2026Q2-third"
    for e in stages.values():
        assert (e.reference_start, e.reference_end) == (date(2026, 4, 1), date(2026, 6, 30))
        assert e.source == "bea" and e.calendar_snapshot_id == "cal_bea_fixture"


def test_combined_release_yields_one_event_per_family() -> None:
    snap = _snap()
    oct29 = [e for e in snap.events if e.scheduled_at == datetime(2026, 10, 29, 8, 30, tzinfo=NY)]
    assert sorted(e.release_id for e in oct29) == ["GDP-2026Q3-advance", "PCE-2026-09"]
    pce = snap.for_family("PCE")
    assert [e.reference_start for e in pce] == [date(2026, 8, 1), date(2026, 9, 1)]
    assert all(e.release_stage is ReleaseStage.INITIAL for e in pce)
    assert snap.skipped_titles == (
        "U.S. International Trade in Goods and Services, September 2026",
    )


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        (
            "GDP (Advance Estimate), 3rd Quarter 2026",
            ("GDP", ReleaseStage.ADVANCE, date(2026, 7, 1)),
        ),
        (
            "Gross Domestic Product, First Quarter 2027 (Second Estimate)",
            ("GDP", ReleaseStage.SECOND, date(2027, 1, 1)),
        ),
        (
            "GDP, 4th Quarter and Year 2026 (Third Estimate)",
            ("GDP", ReleaseStage.THIRD, date(2026, 10, 1)),
        ),
        (
            "GDP, 2nd Quarter 2026 (Comprehensive Update)",
            ("GDP", ReleaseStage.BENCHMARK_REVISION, date(2026, 4, 1)),
        ),
        (
            "Personal Income and Outlays, December 2026",
            ("PCE", ReleaseStage.INITIAL, date(2026, 12, 1)),
        ),
    ],
)
def test_title_classification(title: str, expected: tuple[str, ReleaseStage, date]) -> None:
    ((family, start, _end, stage, _rid),) = classify_title(title)
    assert (family, stage, start) == expected


def test_unrecognised_gdp_title_skipped_not_guessed() -> None:
    assert classify_title("GDP by State, 2nd Quarter 2026") == []


def test_stage_order_enforced() -> None:
    rows = [
        ("GDP (Advance Estimate), 2nd Quarter 2026", datetime(2026, 8, 27, 8, 30, tzinfo=NY)),
        ("GDP (Second Estimate), 2nd Quarter 2026", datetime(2026, 7, 30, 8, 30, tzinfo=NY)),
    ]
    with pytest.raises(BeaScheduleError, match="chronological order"):
        parse_bea_schedule_rows(rows, calendar_snapshot_id="c", retrieved_at=RETRIEVED)


def test_conflicting_duplicate_stage_rejected() -> None:
    rows = [
        ("GDP (Advance Estimate), 2nd Quarter 2026", datetime(2026, 7, 30, 8, 30, tzinfo=NY)),
        ("GDP (Advance Estimate), 2nd Quarter 2026", datetime(2026, 7, 31, 8, 30, tzinfo=NY)),
    ]
    with pytest.raises(BeaScheduleError, match="conflicting"):
        parse_bea_schedule_rows(rows, calendar_snapshot_id="c", retrieved_at=RETRIEVED)


def test_naive_row_times_rejected() -> None:
    with pytest.raises(BeaScheduleError, match="timezone-aware"):
        parse_bea_schedule_rows(
            [("GDP (Advance Estimate), 2nd Quarter 2026", datetime(2026, 7, 30, 8, 30))],
            calendar_snapshot_id="c",
            retrieved_at=RETRIEVED,
        )


def test_scheduled_not_actual_unless_confirmed() -> None:
    assert all(e.actual_release_at is None for e in _snap().events)
    confirmed = _snap(confirm_past_events=True, confirmation_lag=timedelta(days=1))
    by_id = {e.release_id: e for e in confirmed.events}
    assert by_id["GDP-2026Q2-advance"].actual_release_at == datetime(2026, 7, 30, 8, 30, tzinfo=NY)
    stamp = by_id["GDP-2026Q2-advance"].to_availability_stamp(resolver_version="t")
    assert stamp.available_at.astimezone(UTC).hour == 12


def test_fetch_requires_explicit_url() -> None:
    body = (FIX / "schedule.ics").read_bytes()
    http = HttpClient(
        "bea",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)),
        sleep=lambda s: None,
        clock=lambda: RETRIEVED,
    )
    snap = fetch_bea_calendar(http, "https://schedule.example.test/bea.ics")
    assert snap.calendar_snapshot_id.startswith("raw_bea_")
    assert len(snap.events) == 6
