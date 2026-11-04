"""Volatility-targeted portfolio (Task 5.11)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from macrosignal.domain import CashReturnSpec
from macrosignal.portfolio.allocation import TargetWeights
from macrosignal.portfolio.risk import CovarianceEstimate
from macrosignal.portfolio.vol_target import VolTargetSettings, ex_ante_vol, vol_target

NY = ZoneInfo("America/New_York")
SESSION = date(2026, 6, 1)
EST = CovarianceEstimate(
    fit_time=datetime(2026, 6, 1, 9, 0, tzinfo=NY),
    rebalance_session=SESSION,
    method="sample",
    assets=("SPY", "TLT"),
    excluded={},
    window_start=date(2025, 6, 2),
    window_end=date(2026, 5, 29),
    n_observations=250,
    periods_per_year=252,
    covariance=((0.04, -0.006), (-0.006, 0.0225)),  # vols 20% / 15%, corr -0.2
)


def _base(weights: dict[str, float]) -> TargetWeights:
    return TargetWeights(
        session=SESSION,
        method="equal_weight",
        weights=weights,
        cash_weight=1 - sum(weights.values()),
        cash_policy=CashReturnSpec(mode="zero"),
    )


def test_scales_down_to_target() -> None:
    base = _base({"SPY": 0.5, "TLT": 0.5})
    sigma = ex_ante_vol(base.weights, EST)
    out, d = vol_target(base, EST, VolTargetSettings(target_vol=0.05))
    assert d.ex_ante_vol_base == pytest.approx(sigma)
    assert d.ex_ante_vol_final == pytest.approx(0.05)
    assert out.cash_weight == pytest.approx(1 - 0.05 / sigma)
    assert d.risk_fit_time == EST.fit_time and d.risk_window == (EST.window_start, EST.window_end)


def test_no_leverage_beyond_caps() -> None:
    base = _base({"SPY": 0.3, "TLT": 0.3})
    out, d = vol_target(base, EST, VolTargetSettings(target_vol=0.30))
    assert d.capped and d.applied_scale == pytest.approx(1.0)
    assert sum(out.weights.values()) == pytest.approx(0.6)
    lev, d2 = vol_target(
        base, EST, VolTargetSettings(target_vol=0.30, max_scale=3.0, max_gross=1.0)
    )
    assert sum(lev.weights.values()) == pytest.approx(1.0) and d2.capped


def test_safe_fallbacks() -> None:
    base = _base({"SPY": 0.5, "GLD": 0.5})
    unscaled, d = vol_target(base, EST, VolTargetSettings(target_vol=0.1))
    assert unscaled.weights == base.weights and "GLD" in (d.fallback_used or "")
    cash, d2 = vol_target(base, None, VolTargetSettings(target_vol=0.1, fallback="cash"))
    assert cash.weights == {} and cash.cash_weight == 1.0 and d2.fallback_used
    flat, d3 = vol_target(_base({}), EST, VolTargetSettings(target_vol=0.1))
    assert flat.cash_weight == 1.0 and d3.applied_scale == 0.0


def test_future_estimate_rejected() -> None:
    late = EST.model_copy(update={"rebalance_session": date(2026, 6, 2)})
    with pytest.raises(ValueError, match="after the rebalance"):
        vol_target(_base({"SPY": 1.0}), late, VolTargetSettings(target_vol=0.1))
