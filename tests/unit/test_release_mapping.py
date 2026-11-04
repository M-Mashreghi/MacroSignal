"""Release-family / series mapping registry (Task 2.6)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from macrosignal.config import load_config_file
from macrosignal.config.models import MacroSeriesRegistry, ReleaseMap
from macrosignal.data.fred_observations import vintage_availability
from macrosignal.domain import Frequency, MacroObservation, ReleaseEvent, ReleaseStage
from macrosignal.pit.release_mapping import (
    AmbiguousMappingError,
    MappingConflictError,
    ReleaseMappingRegistry,
)

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")


def _configs() -> tuple[MacroSeriesRegistry, ReleaseMap]:
    reg = load_config_file(ROOT / "configs/series/us_macro_v1.yaml", MacroSeriesRegistry)
    rmap = load_config_file(ROOT / "configs/series/release_map_v2.yaml", ReleaseMap)
    return reg, rmap


def _mapping() -> ReleaseMappingRegistry:
    return ReleaseMappingRegistry(*_configs())


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
        "calendar_snapshot_id": "cal_1",
        "source_timezone": "America/New_York",
        "scheduled_at": datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        "actual_release_at": datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        "reference_start": date(2026, 9, 1),
        "reference_end": date(2026, 9, 30),
        "release_stage": "initial",
    }
    data.update(kw)
    return ReleaseEvent.model_validate(data)


def test_configured_series_are_mapped() -> None:
    m = _mapping()
    cpi = m.for_key("headline_cpi")
    assert cpi.release_family == "CPI" and cpi.official_source == "BLS"
    assert cpi.reference_frequency is Frequency.MONTHLY
    gdp = m.for_series("fred_alfred", "GDPC1")
    assert gdp.release_stages[0] is ReleaseStage.ADVANCE
    assert gdp.canonical_stage(ReleaseStage.INITIAL) is ReleaseStage.ADVANCE
    assert not m.for_key("industrial_production").has_official_release
    assert m.mapping_id.startswith("release_map_v2_")
    assert len(m.mappings()) == len(_configs()[0].series)


def test_mapping_id_versioned_separately_from_adapters() -> None:
    reg, rmap = _configs()
    v1 = load_config_file(ROOT / "configs/series/release_map_v1.yaml", ReleaseMap)
    assert (
        ReleaseMappingRegistry(reg, v1).mapping_id != ReleaseMappingRegistry(reg, rmap).mapping_id
    )
    assert ReleaseMappingRegistry(reg, rmap).mapping_id == _mapping().mapping_id


def test_series_claimed_twice_rejected() -> None:
    reg, rmap = _configs()
    data = rmap.model_dump()
    data["release_families"]["PCE"]["series_keys"].append("headline_cpi")
    with pytest.raises(AmbiguousMappingError, match="several families"):
        ReleaseMappingRegistry(reg, ReleaseMap.model_validate(data))


def test_registry_and_map_must_agree() -> None:
    reg, rmap = _configs()
    data = rmap.model_dump()
    data["release_families"]["CPI"]["series_keys"].remove("core_cpi")
    with pytest.raises(AmbiguousMappingError, match="core_cpi"):
        ReleaseMappingRegistry(reg, ReleaseMap.model_validate(data))
    reg_data = reg.model_dump()
    reg_data["series"].append({**reg_data["series"][0], "key": "cpi_copy"})
    reg_data["series"][-1]["release_family"] = None
    with pytest.raises(AmbiguousMappingError, match="several keys"):
        ReleaseMappingRegistry(MacroSeriesRegistry.model_validate(reg_data), rmap)


def test_match_unique_event() -> None:
    event = _mapping().match_event(
        _obs(),
        [
            _event(),
            _event(
                release_id="CPI-2026-08",
                reference_start=date(2026, 8, 1),
                reference_end=date(2026, 8, 31),
            ),
        ],
    )
    assert event is not None and event.release_id == "CPI-2026-09"


def test_no_event_leaves_observation_date_level() -> None:
    m = _mapping()
    assert m.match_event(_obs(), []) is None
    assert m.match_event(_obs(release_stage="revision"), [_event()]) is None
    assert m.match_event(_obs(), [_event(actual_release_at=None)]) is None
    indpro = _obs(series_id="INDPRO")
    assert m.match_event(indpro, [_event()]) is None


def test_ambiguous_events_rejected() -> None:
    with pytest.raises(AmbiguousMappingError, match="2 CPI events"):
        _mapping().match_event(_obs(), [_event(), _event(release_id="CPI-2026-09-dup")])


def test_conflicting_dates_rejected() -> None:
    late = _event(actual_release_at=datetime(2026, 10, 16, 8, 30, tzinfo=NY))
    with pytest.raises(MappingConflictError, match="vintage date"):
        _mapping().match_event(_obs(), [late])


def test_reference_period_rules() -> None:
    cpi = _mapping().for_key("headline_cpi")
    assert (
        cpi.reference_period_problem(date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 15))
        is None
    )
    assert "monthly" in (
        cpi.reference_period_problem(date(2026, 7, 1), date(2026, 9, 30), date(2026, 10, 15)) or ""
    )
    assert "bound" in (
        cpi.reference_period_problem(date(2026, 1, 1), date(2026, 1, 31), date(2026, 6, 1)) or ""
    )
    assert "not after" in (
        cpi.reference_period_problem(date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 30)) or ""
    )
    gdp = _mapping().for_key("real_gdp")
    assert "quarterly" in (
        gdp.reference_period_problem(date(2026, 5, 1), date(2026, 7, 31), date(2026, 8, 30)) or ""
    )


def test_gdp_initial_matches_advance_event() -> None:
    obs = _obs(
        series_id="GDPC1",
        reference_start=date(2026, 4, 1),
        reference_end=date(2026, 6, 30),
        frequency="quarterly",
        seasonal_adjustment="seasonally_adjusted_annual_rate",
        availability=vintage_availability(date(2026, 7, 30)),
        vintage_date=date(2026, 7, 30),
        realtime_start=date(2026, 7, 30),
    )
    event = _event(
        release_id="GDP-2026Q2-adv",
        release_family="GDP",
        scheduled_at=datetime(2026, 7, 30, 8, 30, tzinfo=NY),
        actual_release_at=datetime(2026, 7, 30, 8, 30, tzinfo=NY),
        reference_start=date(2026, 4, 1),
        reference_end=date(2026, 6, 30),
        release_stage="advance",
    )
    assert _mapping().match_event(obs, [event]) == event
