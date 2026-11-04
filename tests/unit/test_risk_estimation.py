"""Ex-ante volatility & covariance estimation (Task 5.4)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import ResearchReturnSpec
from macrosignal.portfolio.returns import AssetReturnSeries, SessionReturn
from macrosignal.portfolio.risk import RiskEstimationError, RiskSettings, estimate_covariance

NY = ZoneInfo("America/New_York")
CAL = UsTradingCalendar()
SPEC = ResearchReturnSpec(
    convention="adjusted_close_to_adjusted_close",
    price_field="adjusted_close",
    adjustment_policy="split_and_dividend_adjusted",
)
SESSIONS = CAL.sessions(date(2025, 1, 2), date(2026, 6, 30))
REBAL = date(2026, 3, 2)
FIT = datetime(2026, 3, 2, 9, 0, tzinfo=NY)


def _series(asset: str, values: np.ndarray, start: int = 0) -> AssetReturnSeries:
    rets = tuple(
        SessionReturn(session=SESSIONS[i + 1], previous_session=SESSIONS[i], simple_return=float(v))
        for i, v in zip(range(start, start + len(values)), values, strict=False)
        if i + 1 < len(SESSIONS)
    )
    return AssetReturnSeries(
        asset_id=asset,
        spec=SPEC,
        returns=rets,
        missing_sessions=(),
        suspicious_moves=(),
        max_abs_return=0.35,
    )


RNG = np.random.default_rng(0)
COMMON = RNG.normal(0, 0.01, len(SESSIONS))
RETURNS = {
    "SPY": _series("SPY", COMMON + RNG.normal(0, 0.005, len(SESSIONS))),
    "TLT": _series("TLT", -0.5 * COMMON + RNG.normal(0, 0.008, len(SESSIONS))),
    "GLD": _series("GLD", RNG.normal(0, 0.01, 100), start=len(SESSIONS) - 120),  # short history
}


def test_uses_only_returns_before_rebalance() -> None:
    est = estimate_covariance(RETURNS, REBAL, FIT, RiskSettings(method="sample", lookback=126))
    assert est.window_end < REBAL and est.n_observations == 126
    shocked = dict(RETURNS)
    spy = RETURNS["SPY"]
    shocked["SPY"] = spy.model_copy(
        update={
            "returns": tuple(
                r if r.session < REBAL else r.model_copy(update={"simple_return": 0.5})
                for r in spy.returns
            )
        }
    )
    assert (
        estimate_covariance(shocked, REBAL, FIT, RiskSettings(method="sample", lookback=126)) == est
    )


def test_short_history_assets_excluded() -> None:
    est = estimate_covariance(RETURNS, REBAL, FIT)
    assert est.assets == ("SPY", "TLT")
    assert "GLD" in est.excluded
    later = estimate_covariance(
        RETURNS,
        date(2026, 6, 30),
        FIT.replace(month=6, day=30),
        RiskSettings(min_observations=20, lookback=60),
    )
    assert "GLD" in later.assets


def test_methods_and_annualization() -> None:
    sample = estimate_covariance(RETURNS, REBAL, FIT, RiskSettings(method="sample", lookback=200))
    lw = estimate_covariance(RETURNS, REBAL, FIT, RiskSettings(method="ledoit_wolf", lookback=200))
    ewma = estimate_covariance(
        RETURNS, REBAL, FIT, RiskSettings(method="ewma", lookback=200, halflife=30)
    )
    assert lw.shrinkage is not None and 0 <= lw.shrinkage <= 1
    for e in (sample, lw, ewma):
        m = e.matrix
        assert np.allclose(m, m.T) and np.all(np.linalg.eigvalsh(m) > 0)
    assert sample.volatilities["SPY"] == pytest.approx(
        np.sqrt(0.01**2 + 0.005**2) * np.sqrt(252), rel=0.2
    )
    assert sample.matrix[0, 1] < 0  # TLT hedges SPY in the synthetic data


def test_errors() -> None:
    with pytest.raises(RiskEstimationError, match="no asset"):
        estimate_covariance(RETURNS, SESSIONS[5], FIT)
    with pytest.raises(RiskEstimationError, match="timezone-aware"):
        estimate_covariance(RETURNS, REBAL, datetime(2026, 3, 2))
