"""Availability resolver and precision hierarchy (Task 2.11)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from macrosignal.config import load_config_file
from macrosignal.config.models import MacroSeriesRegistry, ReleaseMap
from macrosignal.data.fred_observations import vintage_availability
from macrosignal.domain import (
    AvailabilityPrecision,
    AvailabilitySource,
    MacroObservation,
    ReleaseEvent,
)
from macrosignal.pit.availability_resolver import (
    RESOLVER_VERSION,
    AvailabilityResolver,
    ResolutionRule,
    meets_precision,
)
from macrosignal.pit.release_mapping import ReleaseMappingRegistry

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")


def _mapping() -> ReleaseMappingRegistry:
    return ReleaseMappingRegistry(
        load_config_file(ROOT / "configs/series/us_macro_v1.yaml", MacroSeriesRegistry),
        load_config_file(ROOT / "configs/series/release_map_v2.yaml", ReleaseMap),
    )


def _obs(**kw: Any) -> MacroObservation:
    data: dict[str, Any] = {
        "source": "fred_alfred",
        "series_id": "CPIAUCSL",
        "retrieved_at": datetime(2026, 11, 1, tzinfo=UTC),
        "source_snapshot_id": "raw_fred_x",
        "adapter_version": "t",
        "release_stage": "initial",
        "reference_start": date(2026, 9, 1),
        "reference_end": date(2026, 9, 30),
        "value": 1.0,
        "units": "index",
        "frequency": "monthly",
        "seasonal_adjustment": "seasonally_adjusted",
        "availability": vintage_availability(date(2026, 10, 15)),
        "vintage_date": date(2026, 10, 15),
        "realtime_start": date(2026, 10, 15),
    }
    data.update(kw)
    return MacroObservation.model_validate(data)


def _event(**kw: Any) -> ReleaseEvent:
    data: dict[str, Any] = {
        "release_id": "CPI-2026-09",
        "release_family": "CPI",
        "release_name": "CPI",
        "source": "bls",
        "calendar_snapshot_id": "cal_bls_1",
        "source_timezone": "America/New_York",
        "scheduled_at": datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        "actual_release_at": datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        "reference_start": date(2026, 9, 1),
        "reference_end": date(2026, 9, 30),
        "release_stage": "initial",
    }
    data.update(kw)
    return ReleaseEvent.model_validate(data)


def test_calendar_mapping_upgrades_to_exact() -> None:
    r = AvailabilityResolver(_mapping(), [_event()]).resolve(_obs())
    assert r.rule is ResolutionRule.OFFICIAL_CALENDAR_EXACT
    stamp = r.availability
    assert stamp.precision is AvailabilityPrecision.EXACT_TIMESTAMP
    assert stamp.available_at == datetime(2026, 10, 15, 8, 30, tzinfo=NY)
    assert stamp.availability_source is AvailabilitySource.ALFRED_VINTAGE_DATE
    assert stamp.calendar_mapping_id is not None
    assert stamp.calendar_mapping_id.startswith(_mapping().mapping_id + "/cal_bls_1/CPI-2026-09")
    assert stamp.resolver_version == RESOLVER_VERSION
    assert r.observation.release_timestamp == stamp.available_at
    assert r.release_id == "CPI-2026-09"
    assert r.raw_timing["precision"] == "release_date_only"


def test_no_event_keeps_conservative_end_of_day() -> None:
    r = AvailabilityResolver(_mapping(), []).resolve(_obs())
    assert r.rule is ResolutionRule.VINTAGE_DATE_CONSERVATIVE_EOD
    assert r.availability.available_at == datetime(2026, 10, 15, 23, 59, 59, tzinfo=NY)
    assert r.precision is AvailabilityPrecision.RELEASE_DATE_ONLY
    assert r.rejected_mapping_reason is None


def test_scheduled_only_event_is_not_used() -> None:
    r = AvailabilityResolver(_mapping(), [_event(actual_release_at=None)]).resolve(_obs())
    assert r.rule is ResolutionRule.VINTAGE_DATE_CONSERVATIVE_EOD


def test_conflicting_event_rejected_and_reason_recorded() -> None:
    late = _event(
        actual_release_at=datetime(2026, 10, 16, 8, 30, tzinfo=NY),
        scheduled_at=datetime(2026, 10, 16, 8, 30, tzinfo=NY),
    )
    r = AvailabilityResolver(_mapping(), [late]).resolve(_obs())
    assert r.rule is ResolutionRule.VINTAGE_DATE_CONSERVATIVE_EOD
    assert r.rejected_mapping_reason is not None and "vintage date" in r.rejected_mapping_reason
    dup = AvailabilityResolver(_mapping(), [_event(), _event(release_id="CPI-2026-09b")])
    assert "events match" in (dup.resolve(_obs()).rejected_mapping_reason or "")


def test_unmapped_series_without_family_stays_date_level() -> None:
    r = AvailabilityResolver(_mapping(), [_event()]).resolve(_obs(series_id="INDPRO"))
    assert r.rule is ResolutionRule.VINTAGE_DATE_CONSERVATIVE_EOD
    unknown_series = AvailabilityResolver(_mapping(), []).resolve(_obs(series_id="NOT_CONFIGURED"))
    assert "unmapped" in (unknown_series.rejected_mapping_reason or "")


def test_conservative_never_moves_earlier() -> None:
    later = _obs(
        availability={
            "available_at": datetime(2026, 10, 16, 9, 0, tzinfo=NY),
            "precision": "inferred_eod",
            "raw_available_date": date(2026, 10, 15),
        }
    )
    r = AvailabilityResolver(_mapping(), []).resolve(later)
    assert r.availability.available_at == datetime(2026, 10, 16, 9, 0, tzinfo=NY)


def test_source_exact_stamp_kept_and_unknown_flagged() -> None:
    exact = _obs(
        series_id="INDPRO",
        availability={
            "available_at": datetime(2026, 10, 15, 9, 15, tzinfo=NY),
            "precision": "provider_timestamp",
            "availability_source": "provider_timestamp",
        },
    )
    assert AvailabilityResolver(_mapping(), []).resolve(exact).rule is ResolutionRule.SOURCE_STAMP
    unknown = _obs(
        series_id="INDPRO",
        vintage_date=None,
        realtime_start=None,
        availability={"available_at": datetime(2026, 10, 20, tzinfo=NY), "precision": "unknown"},
    )
    r = AvailabilityResolver(_mapping(), []).resolve(unknown)
    assert r.rule is ResolutionRule.UNKNOWN and r.precision is AvailabilityPrecision.UNKNOWN


def test_precision_hierarchy() -> None:
    P = AvailabilityPrecision
    assert meets_precision(P.EXACT_TIMESTAMP, P.RELEASE_DATE_ONLY)
    assert meets_precision(P.RELEASE_DATE_ONLY, P.RELEASE_DATE_ONLY)
    assert not meets_precision(P.INFERRED_EOD, P.RELEASE_DATE_ONLY)
    assert not meets_precision(P.UNKNOWN, P.INFERRED_EOD)


def test_resolve_all_preserves_order_and_pit() -> None:
    obs = [_obs(), _obs(series_id="INDPRO")]
    out = AvailabilityResolver(_mapping(), [_event()]).resolve_all(obs)
    assert [o.observation.series_id for o in out] == ["CPIAUCSL", "INDPRO"]
    morning = datetime(2026, 10, 15, 9, 0, tzinfo=NY)
    assert out[0].observation.is_available_at(morning)
    assert not out[1].observation.is_available_at(morning)


@pytest.mark.parametrize("stage", ["revision"])
def test_revisions_without_stage_event_stay_date_level(stage: str) -> None:
    r = AvailabilityResolver(_mapping(), [_event()]).resolve(_obs(release_stage=stage))
    assert r.rule is ResolutionRule.VINTAGE_DATE_CONSERVATIVE_EOD
