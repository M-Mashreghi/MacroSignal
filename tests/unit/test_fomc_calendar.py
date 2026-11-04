"""FOMC meeting / statement event calendar (Task 2.9)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from macrosignal.calendar.fomc import (
    FOMC_FAMILY,
    FomcScheduleError,
    PolicyEventKind,
    parse_fomc_schedule,
    policy_surprise,
)
from macrosignal.domain import ConsensusExpectation, ExpectationChronologyError, ModelForecast

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "fomc" / "schedule.csv"
NY = ZoneInfo("America/New_York")
RETRIEVED = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
HEADER = (
    "meeting_start,meeting_end,statement_scheduled_at,statement_released_at,"
    "unscheduled,has_projections\n"
)


def _snap(text: str | None = None):  # type: ignore[no-untyped-def]
    return parse_fomc_schedule(
        text if text is not None else FIX.read_text(encoding="utf-8"), retrieved_at=RETRIEVED
    )


def test_meetings_and_statement_events() -> None:
    snap = _snap()
    assert [m.meeting_id for m in snap.meetings] == [
        "FOMC-2026-09-16",
        "FOMC-2026-10-28",
        "FOMC-2026-12-09",
    ]
    oct_ = snap.meetings[1]
    assert oct_.event_kind is PolicyEventKind.POLICY_STATEMENT
    assert oct_.statement.release_family == FOMC_FAMILY
    assert oct_.statement_time == datetime(2026, 10, 28, 14, 0, tzinfo=NY)
    assert oct_.statement.scheduled_at_utc == datetime(2026, 10, 28, 18, 0, tzinfo=UTC)
    assert oct_.statement.reference_start is None and oct_.statement.release_stage is None
    assert snap.meetings[0].has_projections and not oct_.has_projections
    assert snap.meeting_on(date(2026, 10, 27)) == oct_
    assert snap.meeting_on(date(2026, 10, 29)) is None
    assert snap.meetings[2].statement_time is None  # future meeting: scheduled only
    assert len(snap.statement_events()) == 3


def test_statement_can_become_exact_availability() -> None:
    stamp = _snap().meetings[1].statement.to_availability_stamp(resolver_version="t")
    assert stamp.available_at == datetime(2026, 10, 28, 14, 0, tzinfo=NY)


@pytest.mark.parametrize(
    ("row", "match"),
    [
        ("2026-10-27,2026-10-28,2026-10-28T14:00:00,,false,false", "no timezone"),
        ("2026-10-27,2026-10-28,2026-10-27T14:00:00-04:00,,false,false", "last meeting day"),
        ("2026-10-28,2026-10-27,2026-10-27T14:00:00-04:00,,false,false", "before meeting_start"),
        ("2026-10-27,2026-10-28,2026-10-28T14:00:00-04:00,,maybe,false", "true/false"),
        (
            "2026-12-08,2026-12-09,2026-12-09T14:00:00-05:00,2026-12-09T14:00:00-05:00,false,false",
            "after the snapshot time",
        ),
    ],
)
def test_bad_rows_rejected(row: str, match: str) -> None:
    with pytest.raises(FomcScheduleError, match=match):
        _snap(HEADER + row + "\n")


def test_missing_columns_and_overlaps_rejected() -> None:
    with pytest.raises(FomcScheduleError, match="missing columns"):
        _snap("meeting_start,meeting_end\n2026-01-01,2026-01-02\n")
    overlap = HEADER + (
        "2026-10-27,2026-10-28,2026-10-28T14:00:00-04:00,,false,false\n"
        "2026-10-28,2026-10-28,2026-10-28T16:00:00-04:00,,true,false\n"
    )
    with pytest.raises(FomcScheduleError, match="overlapping"):
        _snap(overlap)


def test_snapshot_id_tracks_content() -> None:
    a = _snap()
    b = _snap(FIX.read_text(encoding="utf-8").replace("false,false", "true,false", 1))
    assert a.calendar_snapshot_id != b.calendar_snapshot_id
    assert all(e.calendar_snapshot_id == a.calendar_snapshot_id for e in a.statement_events())


def _expectation(**kw: Any) -> ConsensusExpectation:
    ts = datetime(2026, 10, 27, 17, 0, tzinfo=NY)
    data: dict[str, Any] = {
        "release_id": "FOMC-2026-10-28",
        "reference_start": date(2026, 10, 28),
        "reference_end": date(2026, 10, 28),
        "expected_value": 3.875,
        "units": "percent_midpoint",
        "expectation_source": "user_consensus_csv",
        "forecast_created_at": ts,
        "availability": {"available_at": ts, "precision": "provider_timestamp"},
        "source_snapshot_id": "exp_1",
    }
    data.update(kw)
    return ConsensusExpectation.model_validate(data)


def test_no_surprise_without_expectation() -> None:
    assert policy_surprise(_snap().meetings[1], 3.875, None) is None


def test_surprise_requires_pre_meeting_consensus() -> None:
    meeting = _snap().meetings[1]
    s = policy_surprise(meeting, 3.625, _expectation())
    assert s is not None and s.surprise == pytest.approx(-0.25)
    late_ts = datetime(2026, 10, 28, 14, 5, tzinfo=NY)
    late = _expectation(
        forecast_created_at=late_ts,
        availability={"available_at": late_ts, "precision": "provider_timestamp"},
    )
    with pytest.raises(ExpectationChronologyError):
        policy_surprise(meeting, 3.625, late)
    with pytest.raises(ValueError, match="not FOMC-2026-10-28"):
        policy_surprise(meeting, 3.625, _expectation(release_id="FOMC-2026-09-16"))
    with pytest.raises(ValueError, match="older than"):
        policy_surprise(meeting, 3.625, _expectation(), max_expectation_age=timedelta(hours=1))
    with pytest.raises(ValueError, match="no recorded statement"):
        policy_surprise(_snap().meetings[2], 3.625, _expectation(release_id="FOMC-2026-12-09"))


def test_model_forecast_cannot_be_policy_surprise() -> None:
    ts = datetime(2026, 10, 27, 17, 0, tzinfo=NY)
    forecast = ModelForecast(
        release_id="FOMC-2026-10-28",
        reference_start=date(2026, 10, 28),
        reference_end=date(2026, 10, 28),
        expected_value=3.875,
        units="percent_midpoint",
        expectation_source="m",
        forecast_created_at=ts,
        availability={"available_at": ts, "precision": "provider_timestamp"},  # type: ignore[arg-type]
        source_snapshot_id="s",
        model_id="m",
        model_version="1",
        training_cutoff=ts,
    )
    with pytest.raises(ExpectationChronologyError, match="requires a consensus"):
        policy_surprise(_snap().meetings[1], 3.625, forecast)  # type: ignore[arg-type]
