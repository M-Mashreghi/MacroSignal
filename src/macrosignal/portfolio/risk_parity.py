"""Risk-parity (equal risk contribution) portfolio from ex-ante covariance.

Weights solve the convex problem ``min 0.5 w'Sw - sum_i b_i log w_i`` (equal
budgets ``b_i = 1/N``) with L-BFGS-B, then are normalized to ``invest`` (1.0 by
default); the solution equalizes the risk contributions
``RC_i = w_i (S w)_i / (w'Sw)``.

Universe: assets tradable on the session that also have a risk estimate (the
others are excluded with a reason).  Stability: the covariance is symmetrized
and, if not positive definite, a small diagonal ridge is added (recorded).  If
the optimizer does not converge or contributions are not within
``tolerance`` of equal, the documented fallback is inverse-volatility weights
(flagged).  The ex-ante risk contributions are always reported.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.optimize import minimize  # type: ignore[import-untyped]

from macrosignal.domain import CashReturnSpec
from macrosignal.portfolio.allocation import TargetWeights
from macrosignal.portfolio.risk import CovarianceEstimate
from macrosignal.portfolio.universe import TradableUniverse


class RiskParitySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    invest: float = Field(default=1.0, gt=0, le=1)
    tolerance: float = Field(default=1e-4, gt=0)
    ridge: float = Field(default=1e-8, gt=0)


class RiskParityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    assets: tuple[str, ...]
    risk_contributions: dict[str, float]
    ex_ante_vol: float
    converged: bool
    fallback_inverse_vol: bool
    ridge_added: float
    excluded: dict[str, str]


def risk_contributions(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    total = float(w @ cov @ w)
    return w * (cov @ w) / total


def risk_parity(
    universe: TradableUniverse,
    estimate: CovarianceEstimate,
    cash_policy: CashReturnSpec,
    settings: RiskParitySettings | None = None,
) -> tuple[TargetWeights, RiskParityReport]:
    s = settings or RiskParitySettings()
    if estimate.rebalance_session > universe.date:
        raise ValueError("risk estimate is from after the rebalance session")
    excluded = {a: "no risk estimate" for a in universe.assets if a not in estimate.assets}
    excluded.update(
        {
            a: f"not tradable ({r.value})"
            for a, r in universe.excluded.items()
            if a in estimate.assets
        }
    )
    assets = [a for a in estimate.assets if a in universe.assets]
    if not assets:
        empty = TargetWeights(
            session=universe.date,
            method="risk_parity",
            weights={},
            cash_weight=1.0,
            cash_policy=cash_policy,
            notes=("no assets with risk estimates",),
        )
        return empty, RiskParityReport(
            assets=(),
            risk_contributions={},
            ex_ante_vol=0.0,
            converged=True,
            fallback_inverse_vol=False,
            ridge_added=0.0,
            excluded=excluded,
        )
    idx = [estimate.assets.index(a) for a in assets]
    cov = estimate.matrix[np.ix_(idx, idx)]
    cov = (cov + cov.T) / 2
    ridge = 0.0
    if np.min(np.linalg.eigvalsh(cov)) <= 0:
        ridge = s.ridge * float(np.trace(cov)) / len(assets)
        cov = cov + ridge * np.eye(len(assets))
    n = len(assets)
    budgets = np.full(n, 1.0 / n)
    vol = np.sqrt(np.diag(cov))
    x0 = (1 / vol) / np.sum(1 / vol)

    def objective(w: np.ndarray) -> tuple[float, np.ndarray]:
        sw = cov @ w
        return float(0.5 * w @ sw - budgets @ np.log(w)), sw - budgets / w

    res = minimize(objective, x0, jac=True, method="L-BFGS-B", bounds=[(1e-12, None)] * n)
    w = np.asarray(res.x, dtype=float)
    w = w / w.sum()
    rc = risk_contributions(w, cov)
    converged = bool(res.success) and float(np.max(np.abs(rc - budgets))) <= s.tolerance
    fallback = not converged
    if fallback:
        w = x0
        rc = risk_contributions(w, cov)
    w = w * s.invest
    weights = {a: float(v) for a, v in zip(assets, w, strict=True)}
    notes = ("fallback: inverse-volatility weights",) if fallback else ()
    tw = TargetWeights(
        session=universe.date,
        method="risk_parity",
        weights=weights,
        cash_weight=1.0 - float(w.sum()),
        cash_policy=cash_policy,
        notes=notes,
    )
    return tw, RiskParityReport(
        assets=tuple(assets),
        risk_contributions={a: float(r) for a, r in zip(assets, rc, strict=True)},
        ex_ante_vol=float(np.sqrt(w @ cov @ w)),
        converged=converged,
        fallback_inverse_vol=fallback,
        ridge_added=ridge,
        excluded=excluded,
    )
