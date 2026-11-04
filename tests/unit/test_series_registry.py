"""Macro series registry loader (Task 3.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from macrosignal.config import load_config_file
from macrosignal.config.models import MacroSeriesRegistry, ReleaseMap
from macrosignal.domain import Frequency
from macrosignal.features.series_registry import (
    SeriesRegistryError,
    build_series_catalog,
    load_series_catalog,
)

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "configs/series/us_macro_v2.yaml"
RMAP = ROOT / "configs/series/release_map_v2.yaml"


def _with(mutate: Any) -> SeriesRegistryError:
    data = load_config_file(REG, MacroSeriesRegistry).model_dump()
    mutate(data)
    with pytest.raises(SeriesRegistryError) as info:
        build_series_catalog(
            MacroSeriesRegistry.model_validate(data), load_config_file(RMAP, ReleaseMap)
        )
    return info.value


def _series(data: dict[str, Any], key: str) -> dict[str, Any]:
    return next(s for s in data["series"] if s["key"] == key)


def test_committed_registry_loads_and_resolves() -> None:
    cat = load_series_catalog(REG, RMAP)
    assert cat.registry_version == 3
    cpi = cat.get("headline_cpi")
    assert cpi.mapping.release_family == "CPI"
    assert cpi.reference_frequency is Frequency.MONTHLY
    assert cat.get("real_gdp").reference_frequency is Frequency.QUARTERLY
    assert cat.get("fed_funds").mapping.release_family is None
    assert {s.key for s in cat.by_family("inflation")} == {
        "headline_cpi",
        "core_cpi",
        "pce_price",
        "core_pce_price",
    }
    assert len(cat.pit_required()) == len(cat.series)
    assert cat.release_mapping.mapping_id.startswith("release_map_v2_")
    with pytest.raises(KeyError):
        cat.get("nope")


def test_v1_registry_lacks_timing_policy() -> None:
    with pytest.raises(SeriesRegistryError, match="must declare a timing_policy"):
        load_series_catalog(ROOT / "configs/series/us_macro_v1.yaml", RMAP)


def test_unknown_transformation() -> None:
    err = _with(lambda d: _series(d, "headline_cpi")["transformation_set"].append("log_level"))
    assert "unknown transformation 'log_level'" in str(err)


def test_frequency_specific_transformations() -> None:
    err = _with(lambda d: _series(d, "real_gdp")["transformation_set"].append("mom_pct"))
    assert "needs monthly data" in str(err)
    err = _with(lambda d: _series(d, "headline_cpi")["transformation_set"].append("qoq_annualized"))
    assert "needs quarterly data" in str(err)


def test_staleness_shorter_than_period_rejected() -> None:
    err = _with(lambda d: _series(d, "real_gdp").update(stale_after_days=60))
    assert "shorter than one quarterly period" in str(err)


def test_timing_policy_must_match_family() -> None:
    err = _with(lambda d: _series(d, "fed_funds").update(timing_policy="release_calendar"))
    assert "requires a mapped release family" in str(err)
    err = _with(lambda d: _series(d, "payrolls").update(timing_policy="vintage_date_conservative"))
    assert "use timing_policy 'release_calendar'" in str(err)
    err = _with(lambda d: _series(d, "fed_funds").update(timing_policy=None))
    assert "fed_funds: PIT-required series must declare" in str(err)


def test_pit_required_needs_vintage_provider() -> None:
    err = _with(lambda d: _series(d, "fed_funds").update(provider="csv_upload"))
    assert "vintage-aware provider" in str(err)


def test_all_problems_reported_together() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _series(d, "fed_funds").update(timing_policy=None)
        _series(d, "core_cpi")["transformation_set"].append("bogus")

    err = _with(mutate)
    assert len(err.problems) == 2
