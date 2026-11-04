"""Equal-weight a-priori composite surprise default config."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from macrosignal.config.models import CompositeSurpriseConfig
from macrosignal.domain import SurpriseMode
from macrosignal.features.series_registry import load_series_catalog
from macrosignal.surprises.composite_config import (
    check_against_catalog,
    family_specs,
    load_composite_config,
    macro_composite,
)
from macrosignal.surprises.standardize import StandardizedSurprise, ZStatus, composite_as_of

ROOT = Path(__file__).resolve().parents[2]
CFG_PATH = ROOT / "configs/signals/composite_surprise_v1.yaml"
NY = ZoneInfo("America/New_York")
T = datetime(2026, 6, 1, 9, 0, tzinfo=NY)


def test_committed_default_is_equal_a_priori_and_untuned() -> None:
    cfg = load_composite_config(CFG_PATH)
    assert cfg.weighting == "equal_a_priori" and cfg.tuned_on_data is False
    assert cfg.alternatives_count_as_variants is True
    w = cfg.macro_composite.weights
    assert set(w) == {"inflation", "labor", "growth"}
    assert max(w.values()) - min(w.values()) < 1e-9 and sum(w.values()) == pytest.approx(1.0)
    for fam in cfg.families.values():
        assert len({m.weight for m in fam.members}) == 1  # equal within family
    check_against_catalog(
        cfg,
        load_series_catalog(
            ROOT / "configs/series/us_macro_v2.yaml", ROOT / "configs/series/release_map_v2.yaml"
        ),
    )


def test_schema_guards() -> None:
    data: dict[str, Any] = load_composite_config(CFG_PATH).model_dump()
    with pytest.raises(ValidationError, match="cannot be tuned_on_data"):
        CompositeSurpriseConfig.model_validate({**data, "tuned_on_data": True})
    with pytest.raises(ValidationError, match="sum to 1"):
        bad = {
            **data,
            "macro_composite": {
                **data["macro_composite"],
                "weights": {"inflation": 0.5, "labor": 0.5, "growth": 0.5},
            },
        }
        CompositeSurpriseConfig.model_validate(bad)
    with pytest.raises(ValidationError):
        CompositeSurpriseConfig.model_validate({**data, "alternatives_count_as_variants": False})


def _z(
    feature: str, z: float, mode: SurpriseMode = SurpriseMode.MARKET_SURPRISE
) -> StandardizedSurprise:
    return StandardizedSurprise(
        release_id=f"{feature}-1",
        feature_name=feature,
        mode=mode,
        label=mode.value,
        release_at=T - timedelta(days=5),
        raw_surprise=z,
        z=z,
        status=ZStatus.OK,
        n_prior=24,
        scale=1.0,
        center=0.0,
    )


def test_family_and_macro_composites() -> None:
    cfg = load_composite_config(CFG_PATH)
    specs = family_specs(cfg, SurpriseMode.MARKET_SURPRISE)
    zs = [
        _z("headline_cpi__mom_pct", 1.0),
        _z("core_cpi__mom_pct", 3.0),
        _z("payrolls__mom_diff", 1.0),
        _z("unemployment__mom_diff", 1.0),
    ]
    infl = composite_as_of(specs["inflation"], zs, T)
    labor = composite_as_of(specs["labor"], zs, T)
    growth = composite_as_of(specs["growth"], zs, T)
    assert infl.value == pytest.approx(2.0)
    assert labor.value == pytest.approx(0.0)  # unemployment enters with sign -1
    assert growth.value is None
    macro = macro_composite(cfg, {"inflation": infl, "labor": labor, "growth": growth}, T)
    assert macro.value == pytest.approx(1.0) and macro.missing_families == ("growth",)
    assert macro.variant_id == "composite_surprise_equal_v1"
    only_one = macro_composite(cfg, {"inflation": infl, "growth": growth}, T)
    assert only_one.value is None  # min_families = 2


def test_modes_never_mixed() -> None:
    cfg = load_composite_config(CFG_PATH)
    m = composite_as_of(
        family_specs(cfg, SurpriseMode.MARKET_SURPRISE)["inflation"],
        [_z("headline_cpi__mom_pct", 1.0)],
        T,
    )
    f = composite_as_of(
        family_specs(cfg, SurpriseMode.FORECAST_ERROR)["inflation"],
        [_z("headline_cpi__mom_pct", 1.0, SurpriseMode.FORECAST_ERROR)],
        T,
    )
    with pytest.raises(ValueError, match="one surprise mode"):
        macro_composite(cfg, {"inflation": m, "labor": f}, T)
    with pytest.raises(ValueError, match="not enabled"):
        family_specs(cfg, SurpriseMode.PROXY_SURPRISE)
