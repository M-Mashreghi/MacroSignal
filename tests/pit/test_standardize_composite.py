"""PIT surprise standardization and composite factors (Task 3.14)."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from macrosignal.domain import ExpectationType, SurpriseMode
from macrosignal.surprises.engine import SurpriseRecord, SurpriseStatus
from macrosignal.surprises.standardize import (
    CompositeSpec,
    StandardizationPolicy,
    ZStatus,
    composite_as_of,
    standardize_surprises,
)

NY = ZoneInfo("America/New_York")
T0 = datetime(2024, 1, 12, 8, 30, tzinfo=NY)
RAW = [0.1, -0.2, 0.05, 0.3, -0.1, 0.0, 0.2, -0.3, 0.15, -0.05, 2.5, 0.1]


def _records(
    raw: list[float | None],
    feature: str = "headline_cpi__mom_pct",
    mode: SurpriseMode = SurpriseMode.MARKET_SURPRISE,
    step_days: int = 30,
) -> list[SurpriseRecord]:
    label = {
        SurpriseMode.MARKET_SURPRISE: "market_surprise",
        SurpriseMode.FORECAST_ERROR: "forecast_error",
    }[mode]
    etype = (
        ExpectationType.CONSENSUS
        if mode is SurpriseMode.MARKET_SURPRISE
        else ExpectationType.MODEL_FORECAST
    )
    out = []
    for i, r in enumerate(raw):
        out.append(
            SurpriseRecord(
                release_id=f"{feature}-{i:02d}",
                release_family="CPI",
                series_key=feature.split("__")[0],
                feature_name=feature,
                mode=mode,
                label=label,
                expectation_type=etype,
                status=SurpriseStatus.COMPUTED
                if r is not None
                else SurpriseStatus.MISSING_EXPECTATION,
                release_at=T0 + timedelta(days=step_days * i),
                actual=1.0,
                expected=None if r is None else 1.0 - r,
                raw_surprise=r,
            )
        )
    return out


def test_scale_uses_only_prior_releases() -> None:
    out = standardize_surprises(_records(RAW), StandardizationPolicy(min_history=4))
    assert [o.status for o in out[:4]] == [ZStatus.INSUFFICIENT_HISTORY] * 4
    k = 6
    expected_scale = np.std(RAW[:k], ddof=1)
    assert out[k].scale == pytest.approx(expected_scale)
    assert out[k].z == pytest.approx(RAW[k] / expected_scale)
    assert (
        out[k].n_prior == k and out[k].last_prior_release_id == f"headline_cpi__mom_pct-{k - 1:02d}"
    )


def test_future_outlier_cannot_change_past_z() -> None:
    policy = StandardizationPolicy(min_history=4)
    base = standardize_surprises(_records(RAW[:10]), policy)
    full = standardize_surprises(_records(RAW), policy)
    assert [b.z for b in base] == [f.z for f in full[:10]]


def test_outlier_policy_mad_and_winsor() -> None:
    std = standardize_surprises(_records(RAW), StandardizationPolicy(min_history=4))
    mad = standardize_surprises(
        _records(RAW), StandardizationPolicy(min_history=4, scale_method="mad")
    )
    assert mad[11].scale < std[11].scale  # MAD down-weights the 2.5 outlier in the history
    wins = standardize_surprises(
        _records(RAW), StandardizationPolicy(min_history=4, winsorize_z=3.0)
    )
    assert wins[10].clipped and wins[10].z == pytest.approx(3.0)
    assert wins[10].raw_surprise == 2.5
    rolling = standardize_surprises(_records(RAW), StandardizationPolicy(min_history=4, window=5))
    assert rolling[11].n_prior == 5


def test_missing_raw_and_zero_scale() -> None:
    out = standardize_surprises(
        _records([0.1, None, 0.1, 0.1, 0.1]), StandardizationPolicy(min_history=2)
    )
    assert out[1].status is ZStatus.NO_RAW_SURPRISE
    assert out[2].status is ZStatus.INSUFFICIENT_HISTORY  # the missing one does not count
    assert out[3].status is ZStatus.ZERO_SCALE and out[3].z is None


def test_one_feature_and_mode_at_a_time() -> None:
    mixed = _records(RAW[:3]) + _records(RAW[:3], mode=SurpriseMode.FORECAST_ERROR)
    with pytest.raises(ValueError, match="one feature and one surprise mode"):
        standardize_surprises(mixed, StandardizationPolicy(min_history=2))


def test_composite_with_provenance_and_staleness() -> None:
    policy = StandardizationPolicy(min_history=3)
    cpi = standardize_surprises(_records(RAW), policy)
    core = standardize_surprises(
        _records([x / 2 for x in RAW], feature="core_cpi__mom_pct"), policy
    )
    spec = CompositeSpec(
        "inflation_surprise",
        (("headline_cpi__mom_pct", 2.0), ("core_cpi__mom_pct", 1.0)),
        SurpriseMode.MARKET_SURPRISE,
        max_age_days=45,
        min_members=2,
    )
    t = T0 + timedelta(days=30 * 8 + 1)
    c = composite_as_of(spec, cpi + core, t)
    z_h, z_c = cpi[8].z, core[8].z
    assert c.value == pytest.approx((2 * z_h + z_c) / 3)
    assert [x.release_id for x in c.contributions] == [
        "headline_cpi__mom_pct-08",
        "core_cpi__mom_pct-08",
    ]
    before = composite_as_of(spec, cpi + core, T0 + timedelta(days=30 * 8) - timedelta(minutes=1))
    assert [x.release_id for x in before.contributions][0] == "headline_cpi__mom_pct-07"
    stale = composite_as_of(spec, cpi + core, T0 + timedelta(days=30 * 11 + 60))
    assert stale.value is None and set(stale.missing_members) == {
        "headline_cpi__mom_pct",
        "core_cpi__mom_pct",
    }


def test_composite_refuses_mixed_modes_and_bad_specs() -> None:
    policy = StandardizationPolicy(min_history=3)
    fe = standardize_surprises(_records(RAW, mode=SurpriseMode.FORECAST_ERROR), policy)
    spec = CompositeSpec(
        "inflation_surprise",
        (("headline_cpi__mom_pct", 1.0),),
        SurpriseMode.MARKET_SURPRISE,
        max_age_days=45,
    )
    with pytest.raises(ValueError, match="only accepts market_surprise"):
        composite_as_of(spec, fe, T0 + timedelta(days=400))
    with pytest.raises(ValueError, match="positive"):
        CompositeSpec("x", (("a", 0.0),), SurpriseMode.MARKET_SURPRISE, 30)
    with pytest.raises(ValueError, match="unique"):
        CompositeSpec("x", (("a", 1.0), ("a", 1.0)), SurpriseMode.MARKET_SURPRISE, 30)
