"""AvailabilityStamp provenance rules and ReleaseEvent timing (Task 1.5)."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from macrosignal.domain import (
    AvailabilityPrecision,
    AvailabilitySource,
    AvailabilityStamp,
    ReleaseEvent,
    ReleaseStage,
)

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")


# --- AvailabilityStamp -------------------------------------------------------


def test_full_audit_stamp_round_trips() -> None:
    stamp = AvailabilityStamp(
        available_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        precision="exact_timestamp",
        availability_source="alfred_vintage_date",
        raw_available_date=date(2026, 10, 15),
        calendar_mapping_id="bls_cpi_v1",
        resolver_version="0.1.0",
    )
    assert stamp.availability_source is AvailabilitySource.ALFRED_VINTAGE_DATE
    assert AvailabilityStamp.model_validate_json(stamp.model_dump_json()) == stamp


def test_minimal_stamp_still_valid() -> None:
    stamp = AvailabilityStamp(available_at=datetime(2026, 1, 2, tzinfo=UTC), precision="unknown")
    assert stamp.availability_source is None
    assert stamp.conservative_adjustment == timedelta(0)


def test_date_level_source_cannot_claim_exact_without_mapping() -> None:
    with pytest.raises(ValidationError, match="calendar_mapping_id"):
        AvailabilityStamp(
            available_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY),
            precision="exact_timestamp",
            availability_source="alfred_vintage_date",
        )


def test_mapping_requires_resolver_version() -> None:
    with pytest.raises(ValidationError, match="resolver_version"):
        AvailabilityStamp(
            available_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY),
            precision="exact_timestamp",
            availability_source="official_release_date",
            calendar_mapping_id="bls_cpi_v1",
        )


@pytest.mark.parametrize(
    ("source", "precision"),
    [
        ("official_release_schedule", "release_date_only"),
        ("provider_timestamp", "exact_timestamp"),
        ("conservative_inference", "exact_timestamp"),
        ("unknown", "inferred_eod"),
        ("alfred_vintage_date", "provider_timestamp"),
    ],
)
def test_precision_must_be_supported_by_source(source: str, precision: str) -> None:
    with pytest.raises(ValidationError, match="not supported"):
        AvailabilityStamp(
            available_at=datetime(2026, 10, 15, 23, 59, tzinfo=NY),
            precision=precision,
            availability_source=source,
        )


def test_date_only_cannot_be_midnight_knowledge() -> None:
    with pytest.raises(ValidationError, match="midnight"):
        AvailabilityStamp(
            available_at=datetime(2026, 10, 15, 0, 0, tzinfo=NY),
            precision="release_date_only",
            availability_source="alfred_vintage_date",
            raw_available_date=date(2026, 10, 15),
        )


def test_available_at_cannot_precede_raw_date() -> None:
    with pytest.raises(ValidationError, match="before raw_available_date"):
        AvailabilityStamp(
            available_at=datetime(2026, 10, 14, 23, 59, tzinfo=NY),
            precision="inferred_eod",
            raw_available_date=date(2026, 10, 15),
        )


def test_conservative_adjustment_only_shifts_later() -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        AvailabilityStamp(
            available_at=datetime(2026, 10, 15, 23, 59, tzinfo=NY),
            precision="inferred_eod",
            conservative_adjustment=timedelta(hours=-1),
        )
    stamp = AvailabilityStamp(
        available_at=datetime(2026, 10, 16, 0, 0, tzinfo=NY),
        precision="inferred_eod",
        availability_source="conservative_inference",
        raw_available_date=date(2026, 10, 15),
        conservative_adjustment=timedelta(hours=1),
    )
    assert stamp.raw_available_at == datetime(2026, 10, 15, 23, 0, tzinfo=NY)


def test_stamp_rejects_naive_and_unknown_source() -> None:
    with pytest.raises(ValidationError):
        AvailabilityStamp(available_at=datetime(2026, 10, 15, 8, 30), precision="exact_timestamp")
    with pytest.raises(ValidationError, match="availability_source"):
        AvailabilityStamp(
            available_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY),
            precision="exact_timestamp",
            availability_source="vendor_guess",
        )


def test_pit_check_uses_instants_across_timezones() -> None:
    stamp = AvailabilityStamp(
        available_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY), precision="exact_timestamp"
    )
    assert stamp.is_available_at(datetime(2026, 10, 15, 12, 30, tzinfo=UTC))
    assert not stamp.is_available_at(datetime(2026, 10, 15, 12, 29, tzinfo=UTC))
    with pytest.raises(ValueError, match="timezone-aware"):
        stamp.is_available_at(datetime(2026, 10, 16))


# --- ReleaseEvent ------------------------------------------------------------


def _cpi_event(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "release_id": "CPI-2026-09",
        "release_family": "CPI",
        "release_name": "Consumer Price Index",
        "source": "bls",
        "calendar_snapshot_id": "cal_bls_2026_001",
        "source_timezone": "America/New_York",
        "scheduled_at": datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        "actual_release_at": datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        "reference_start": date(2026, 9, 1),
        "reference_end": date(2026, 9, 30),
        "release_stage": "initial",
    }
    data.update(overrides)
    return data


def test_release_event_utc_and_local_views() -> None:
    event = ReleaseEvent.model_validate(_cpi_event())
    assert event.scheduled_at_utc == datetime(2026, 10, 15, 12, 30, tzinfo=UTC)
    assert event.actual_release_at_local is not None
    assert event.actual_release_at_local.hour == 8
    assert event.is_released
    assert event.deviation_from_schedule == 0.0
    assert event.release_stage is ReleaseStage.INITIAL


def test_dst_handled_by_timezone_database() -> None:
    # 08:30 ET is 12:30 UTC in EDT (October) but 13:30 UTC in EST (December).
    summer = ReleaseEvent.model_validate(_cpi_event())
    winter = ReleaseEvent.model_validate(
        _cpi_event(
            release_id="CPI-2026-11",
            reference_start=date(2026, 11, 1),
            reference_end=date(2026, 11, 30),
            scheduled_at=datetime(2026, 12, 10, 8, 30, tzinfo=NY),
            actual_release_at=datetime(2026, 12, 10, 8, 30, tzinfo=NY),
        )
    )
    assert summer.scheduled_at_utc.hour == 12
    assert winter.scheduled_at_utc.hour == 13


def test_scheduled_and_actual_are_separate() -> None:
    late = ReleaseEvent.model_validate(
        _cpi_event(actual_release_at=datetime(2026, 10, 24, 8, 30, tzinfo=NY))
    )
    assert late.deviation_from_schedule == pytest.approx(9 * 86400)
    stamp = late.to_availability_stamp(resolver_version="0.1.0")
    assert stamp.available_at == datetime(2026, 10, 24, 8, 30, tzinfo=NY)
    assert stamp.precision is AvailabilityPrecision.EXACT_TIMESTAMP
    assert stamp.availability_source is AvailabilitySource.OFFICIAL_RELEASE_SCHEDULE
    assert stamp.raw_available_date == date(2026, 10, 24)


def test_unreleased_event_cannot_become_availability() -> None:
    pending = ReleaseEvent.model_validate(_cpi_event(actual_release_at=None))
    assert not pending.is_released
    assert pending.deviation_from_schedule is None
    with pytest.raises(ValueError, match="scheduled time cannot be used"):
        pending.to_availability_stamp(resolver_version="0.1.0")


@pytest.mark.parametrize("field", ["scheduled_at", "actual_release_at"])
def test_naive_release_timestamps_rejected(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        ReleaseEvent.model_validate(_cpi_event(**{field: datetime(2026, 10, 15, 8, 30)}))


@pytest.mark.parametrize("tz", ["Etc/GMT+5", "UTC-5", "EST", "Mars/Olympus", ""])
def test_fixed_offset_or_unknown_timezone_rejected(tz: str) -> None:
    with pytest.raises(ValidationError, match="source_timezone"):
        ReleaseEvent.model_validate(_cpi_event(source_timezone=tz))


def test_release_before_reference_period_end_rejected() -> None:
    with pytest.raises(ValidationError, match="not after the reference period end"):
        ReleaseEvent.model_validate(
            _cpi_event(scheduled_at=datetime(2026, 9, 30, 8, 30, tzinfo=NY))
        )


def test_local_date_used_for_reference_check() -> None:
    # 2026-10-01 01:00 UTC is still 2026-09-30 in New York: not after period end.
    with pytest.raises(ValidationError, match="not after the reference period end"):
        ReleaseEvent.model_validate(
            _cpi_event(actual_release_at=datetime(2026, 10, 1, 1, 0, tzinfo=UTC))
        )


def test_reference_period_pairing() -> None:
    with pytest.raises(ValidationError, match="together"):
        ReleaseEvent.model_validate(_cpi_event(reference_end=None))


def test_fomc_event_without_reference_period() -> None:
    event = ReleaseEvent(
        release_id="FOMC-2026-10-28",
        release_family="FOMC",
        release_name="FOMC Statement",
        source="federal_reserve",
        calendar_snapshot_id="cal_fomc_2026_001",
        source_timezone="America/New_York",
        scheduled_at=datetime(2026, 10, 28, 14, 0, tzinfo=NY),
        actual_release_at=datetime(2026, 10, 28, 14, 0, tzinfo=NY),
    )
    assert event.reference_start is None
    assert event.release_stage is None


def test_release_event_frozen_and_strict() -> None:
    event = ReleaseEvent.model_validate(_cpi_event())
    with pytest.raises(ValidationError):
        event.release_id = "x"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="extra"):
        ReleaseEvent.model_validate(_cpi_event(consensus=3.1))


def test_bundled_release_calendar_fixture_parses() -> None:
    with (ROOT / "examples/release_calendar_fixture.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    for row in rows:
        year, month = (int(x) for x in row["reference_period"].split("-"))
        event = ReleaseEvent(
            release_id=f"{row['release_id']}-{row['reference_period']}",
            release_family=row["release_id"],
            release_name=row["release_name"],
            source="fixture",
            calendar_snapshot_id="fixture_calendar",
            source_timezone=row["source_timezone"],
            scheduled_at=datetime.fromisoformat(row["scheduled_at"]),
            actual_release_at=datetime.fromisoformat(row["actual_release_at"]),
            reference_start=date(year, month, 1),
            reference_end=date(year, month, 28),
            release_stage=row["release_stage"],
        )
        stamp = event.to_availability_stamp(resolver_version="fixture")
        assert stamp.available_at == event.actual_release_at
        assert stamp.available_at.utcoffset() == event.zone.utcoffset(stamp.available_at)
