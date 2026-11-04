"""Timestamped consensus CSV adapter (Task 3.11)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from macrosignal.domain import ReleaseEvent, SurpriseMode
from macrosignal.surprises.consensus_csv import (
    RowProblem,
    import_consensus_csv,
    import_consensus_file,
)
from macrosignal.surprises.expectations import ExpectationService, ExpectationStatus

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
HEADER = (
    "release_id,reference_period,expected_value,forecast_created_at,available_at,"
    "expectation_source,expectation_type,release_stage,units\n"
)

VALID_CPI_ROW = (
    "CPI,2026-09,0.3,2026-10-10T17:00:00-04:00,2026-10-10T17:00:00-04:00,svc,consensus,,percent_mom"
)


def _event(
    rid: str, family: str, start: date, end: date, at: datetime, stage: str = "initial"
) -> ReleaseEvent:
    return ReleaseEvent(
        release_id=rid,
        release_family=family,
        release_name=family,
        source="x",
        calendar_snapshot_id="cal",
        source_timezone="America/New_York",
        scheduled_at=at,
        actual_release_at=at,
        reference_start=start,
        reference_end=end,
        release_stage=stage,
    )


EVENTS = [
    _event(
        "CPI-2026-09",
        "CPI",
        date(2026, 9, 1),
        date(2026, 9, 30),
        datetime(2026, 10, 15, 8, 30, tzinfo=NY),
    ),
    _event(
        "GDP-2026Q3-advance",
        "GDP",
        date(2026, 7, 1),
        date(2026, 9, 30),
        datetime(2026, 10, 29, 8, 30, tzinfo=NY),
        "advance",
    ),
    _event(
        "GDP-2026Q3-second",
        "GDP",
        date(2026, 7, 1),
        date(2026, 9, 30),
        datetime(2026, 11, 25, 8, 30, tzinfo=NY),
        "second",
    ),
]


def test_bundled_template_imports() -> None:
    result = import_consensus_file(
        ROOT / "examples/consensus_template.csv", EVENTS, default_units={"CPI": "percent_mom"}
    )
    assert result.report.rows_total == 1 and result.report.accepted == 1
    exp = result.expectations[0]
    assert exp.release_id == "CPI-2026-09" and exp.units == "percent_mom"
    assert exp.source_snapshot_id.startswith("consensus_")


def test_validation_report_classifies_every_row() -> None:
    rows = [
        "CPI,2026-09,0.3,2026-10-10T17:00:00-04:00,2026-10-10T17:00:00-04:00,svc,consensus,,percent_mom",
        "CPI,2026-09,0.4,2026-10-15T08:30:00-04:00,2026-10-15T08:30:00-04:00,svc,consensus,,percent_mom",
        "CPI,2026-08,0.2,2026-09-01T17:00:00-04:00,2026-09-01T17:00:00-04:00,svc,consensus,,percent_mom",
        "GDP,2026-Q3,2.1,2026-10-20T12:00:00-04:00,2026-10-20T12:00:00-04:00,svc,consensus,,percent_annualized",
        "GDP,2026-Q3,2.0,2026-10-20T12:00:00-04:00,2026-10-20T12:00:00-04:00,svc,consensus,advance,percent_annualized",
        "CPI,2026-09,0.3,2026-10-10T17:00:00,2026-10-10T17:00:00,svc,consensus,,percent_mom",
        "CPI,2026-09,0.3,2026-10-10T17:00:00-04:00,2026-10-10T17:00:00-04:00,model,model_forecast,,percent_mom",
        "CPI,2026-09,abc,2026-10-10T17:00:00-04:00,2026-10-10T17:00:00-04:00,svc,consensus,,percent_mom",
        "PCE,2026-09,0.2,2026-10-10T17:00:00-04:00,2026-10-10T17:00:00-04:00,svc,consensus,,",
    ]
    result = import_consensus_csv(HEADER + "\n".join(rows) + "\n", EVENTS)
    r = result.report
    assert r.rows_total == 9 and r.accepted == 2
    by_line = {i.line: i.problem for i in r.issues}
    assert by_line == {
        3: RowProblem.POST_RELEASE,
        4: RowProblem.UNMATCHED,
        5: RowProblem.AMBIGUOUS,
        7: RowProblem.INVALID,  # naive timestamp
        8: RowProblem.INVALID,  # not a consensus row
        9: RowProblem.INVALID,  # non-numeric value
        10: RowProblem.INVALID,  # no units
    }
    assert {e.release_id for e in result.expectations} == {"CPI-2026-09", "GDP-2026Q3-advance"}


def test_scheduled_only_events_are_not_matched() -> None:
    pending = EVENTS[0].model_copy(update={"actual_release_at": None})
    row = VALID_CPI_ROW
    result = import_consensus_csv(HEADER + row + "\n", [pending])
    assert result.report.count(RowProblem.UNMATCHED) == 1


def test_imported_provider_feeds_expectation_service() -> None:
    row = VALID_CPI_ROW
    imported = import_consensus_csv(HEADER + row + "\n", EVENTS)
    svc = ExpectationService([imported.provider()])
    res = svc.get(EVENTS[0], SurpriseMode.MARKET_SURPRISE, datetime(2026, 10, 15, 8, 30, tzinfo=NY))
    assert res.status is ExpectationStatus.AVAILABLE and res.provider == "consensus_csv"


def test_missing_columns_rejected() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        import_consensus_csv("release_id,expected_value\nCPI,0.1\n", EVENTS)
