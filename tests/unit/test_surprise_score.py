"""Surprise / forecast-error scores with decay (Task 5.6)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from macrosignal.config import load_config_file
from macrosignal.config.models import SignalConfig
from macrosignal.domain import SurpriseMode
from macrosignal.signals.surprise_score import DecayPolicy, SurpriseSensitivityMap, surprise_scores
from macrosignal.surprises.standardize import StandardizedSurprise, ZStatus

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
T0 = datetime(2026, 10, 15, 8, 30, tzinfo=NY)
BETAS = SurpriseSensitivityMap(
    map_id="sens_v1",
    betas={
        "headline_cpi__mom_pct": {"TLT": -1.0, "SPY": -0.5},
        "payrolls__mom_diff": {"SPY": 1.0},
    },
)
DECAY = DecayPolicy.from_config(
    load_config_file(
        ROOT / "configs/signals/signals_v1.yaml", SignalConfig
    ).surprise_component.decay
)


def _z(
    feature: str,
    z: float | None,
    at: datetime,
    rid: str,
    mode: SurpriseMode = SurpriseMode.MARKET_SURPRISE,
) -> StandardizedSurprise:
    return StandardizedSurprise(
        release_id=rid,
        feature_name=feature,
        mode=mode,
        label=mode.value,
        release_at=at,
        raw_surprise=z,
        z=z,
        status=ZStatus.OK if z is not None else ZStatus.INSUFFICIENT_HISTORY,
        n_prior=24,
        scale=1.0,
        center=0.0,
    )


def test_config_decay_policy() -> None:
    assert (DECAY.half_life_days, DECAY.max_age_days) == (10, 45)
    assert DECAY.factor(10) == pytest.approx(0.5) and DECAY.factor(46) == 0.0


def test_scores_decay_with_age() -> None:
    zs = [_z("headline_cpi__mom_pct", 2.0, T0, "CPI-09")]
    s0 = surprise_scores(zs, BETAS, DECAY, T0, ["TLT", "SPY"], SurpriseMode.MARKET_SURPRISE)
    s10 = surprise_scores(
        zs, BETAS, DECAY, T0 + timedelta(days=10), ["TLT"], SurpriseMode.MARKET_SURPRISE
    )
    assert s0["TLT"].score == pytest.approx(-2.0) and s0["SPY"].score == pytest.approx(-1.0)
    assert s10["TLT"].score == pytest.approx(-1.0)
    assert s0["TLT"].contributions[0].release_id == "CPI-09"
    assert "payrolls__mom_diff" in s0["SPY"].missing_factors
    gone = surprise_scores(
        zs, BETAS, DECAY, T0 + timedelta(days=60), ["TLT"], SurpriseMode.MARKET_SURPRISE
    )
    assert gone["TLT"].score == 0.0 and "headline_cpi__mom_pct" in gone["TLT"].missing_factors


def test_newer_release_replaces_older_and_future_ignored() -> None:
    zs = [
        _z("headline_cpi__mom_pct", 2.0, T0, "CPI-09"),
        _z("headline_cpi__mom_pct", -1.0, T0 + timedelta(days=30), "CPI-10"),
    ]
    before = surprise_scores(
        zs, BETAS, DECAY, T0 + timedelta(days=29), ["TLT"], SurpriseMode.MARKET_SURPRISE
    )
    assert before["TLT"].contributions[0].release_id == "CPI-09"
    after = surprise_scores(
        zs, BETAS, DECAY, T0 + timedelta(days=30), ["TLT"], SurpriseMode.MARKET_SURPRISE
    )
    assert len(after["TLT"].contributions) == 1 and after["TLT"].score == pytest.approx(1.0)


def test_missing_z_not_imputed_and_modes_not_mixed() -> None:
    zs = [_z("headline_cpi__mom_pct", None, T0, "CPI-09")]
    s = surprise_scores(zs, BETAS, DECAY, T0, ["TLT"], SurpriseMode.MARKET_SURPRISE)
    assert s["TLT"].score == 0.0 and "headline_cpi__mom_pct" in s["TLT"].missing_factors
    fe = [_z("headline_cpi__mom_pct", 1.0, T0, "CPI-09", SurpriseMode.FORECAST_ERROR)]
    with pytest.raises(ValueError, match="cannot use other surprise modes"):
        surprise_scores(fe, BETAS, DECAY, T0, ["TLT"], SurpriseMode.MARKET_SURPRISE)
    fe_scores = surprise_scores(fe, BETAS, DECAY, T0, ["TLT"], SurpriseMode.FORECAST_ERROR)
    assert fe_scores["TLT"].label == "forecast_error"
