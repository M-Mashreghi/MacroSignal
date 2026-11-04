"""Risk-parity portfolio (Task 5.12)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from macrosignal.domain import CashReturnSpec
from macrosignal.portfolio.risk import CovarianceEstimate
from macrosignal.portfolio.risk_parity import risk_parity
from macrosignal.portfolio.universe import ExclusionReason, TradableUniverse

NY = ZoneInfo("America/New_York")
CASH = CashReturnSpec(mode="zero")
SESSION = date(2026, 6, 1)


def _est(assets: tuple[str, ...], cov: list[list[float]]) -> CovarianceEstimate:
    return CovarianceEstimate(
        fit_time=datetime(2026, 6, 1, 9, tzinfo=NY),
        rebalance_session=SESSION,
        method="ledoit_wolf",
        assets=assets,
        excluded={},
        window_start=date(2025, 6, 2),
        window_end=date(2026, 5, 29),
        n_observations=250,
        periods_per_year=252,
        covariance=tuple(tuple(r) for r in cov),
    )


EST = _est(
    ("GLD", "SPY", "TLT"), [[0.0256, 0.002, 0.001], [0.002, 0.04, -0.006], [0.001, -0.006, 0.0225]]
)
U = TradableUniverse(date=SESSION, assets=("GLD", "SPY", "TLT"), excluded={})


def test_equal_risk_contributions() -> None:
    w, rep = risk_parity(U, EST, CASH)
    assert rep.converged and not rep.fallback_inverse_vol
    assert sum(w.weights.values()) == pytest.approx(1.0)
    assert all(rc == pytest.approx(1 / 3, abs=1e-4) for rc in rep.risk_contributions.values())
    assert w.weights["TLT"] > w.weights["SPY"]  # lower-vol, diversifying asset gets more weight


def test_uncorrelated_case_is_inverse_vol() -> None:
    est = _est(("A", "B"), [[0.04, 0.0], [0.0, 0.01]])
    w, _ = risk_parity(TradableUniverse(date=SESSION, assets=("A", "B"), excluded={}), est, CASH)
    assert w.weights["B"] / w.weights["A"] == pytest.approx(2.0, rel=1e-4)


def test_tradable_universe_and_invest_fraction() -> None:
    u = TradableUniverse(
        date=SESSION,
        assets=("SPY", "TLT", "QQQ"),
        excluded={"GLD": ExclusionReason.BEFORE_INCEPTION},
    )
    from macrosignal.portfolio.risk_parity import RiskParitySettings

    w, rep = risk_parity(u, EST, CASH, RiskParitySettings(invest=0.8))
    assert set(w.weights) == {"SPY", "TLT"}
    assert rep.excluded["QQQ"] == "no risk estimate" and "not tradable" in rep.excluded["GLD"]
    assert w.cash_weight == pytest.approx(0.2)


def test_numerical_stability_with_singular_covariance() -> None:
    est = _est(("A", "B"), [[0.04, 0.04], [0.04, 0.04]])  # perfectly correlated
    w, rep = risk_parity(TradableUniverse(date=SESSION, assets=("A", "B"), excluded={}), est, CASH)
    assert rep.ridge_added > 0
    assert all(np.isfinite(v) for v in w.weights.values()) and sum(
        w.weights.values()
    ) == pytest.approx(1.0)


def test_future_estimate_rejected() -> None:
    with pytest.raises(ValueError, match="after the rebalance"):
        risk_parity(
            TradableUniverse(date=date(2026, 5, 29), assets=("SPY",), excluded={}), EST, CASH
        )
