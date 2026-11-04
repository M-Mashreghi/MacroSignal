"""Volatility-targeted portfolio using ex-ante risk estimates only.

Scales the risky part of a base allocation so its ex-ante annualized
volatility (from the :class:`CovarianceEstimate` fitted at the rebalance,
Task 5.4) equals ``target_vol``:

``scale = target_vol / sigma_base``;  applied scale = ``min(scale, max_scale)``
and gross exposure is capped at ``max_gross`` (``1.0`` = no leverage);
any capital not invested is cash under the declared cash policy.

Safe fallback when risk cannot be estimated (held asset missing from the
estimate, or zero ex-ante volatility): ``fallback = "unscaled"`` keeps the base
weights unchanged (never levered), ``"cash"`` moves everything to cash.  The
diagnostics record target, ex-ante volatility before/after, raw and applied
scale, whether a cap or fallback was used, and the estimate's fit time and
window.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.portfolio.allocation import TargetWeights
from macrosignal.portfolio.risk import CovarianceEstimate


class VolTargetSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_vol: float = Field(gt=0)
    max_scale: float = Field(default=1.0, gt=0)
    max_gross: float = Field(default=1.0, gt=0)
    fallback: Literal["unscaled", "cash"] = "unscaled"


class VolTargetDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session: date
    target_vol: float
    ex_ante_vol_base: float | None
    ex_ante_vol_final: float | None
    raw_scale: float | None
    applied_scale: float
    capped: bool
    fallback_used: str | None
    risk_fit_time: AwareDatetime | None
    risk_window: tuple[date, date] | None


def ex_ante_vol(weights: dict[str, float], estimate: CovarianceEstimate) -> float:
    idx = {a: i for i, a in enumerate(estimate.assets)}
    w = np.zeros(len(estimate.assets))
    for a, v in weights.items():
        w[idx[a]] = v
    return float(np.sqrt(max(w @ estimate.matrix @ w, 0.0)))


def vol_target(
    base: TargetWeights, estimate: CovarianceEstimate | None, settings: VolTargetSettings
) -> tuple[TargetWeights, VolTargetDiagnostics]:
    held = {a: w for a, w in base.weights.items() if w != 0}
    problem = None
    if estimate is None:
        problem = "no risk estimate"
    elif estimate.rebalance_session > base.session:
        raise ValueError("risk estimate is from after the rebalance session")
    elif missing := sorted(set(held) - set(estimate.assets)):
        problem = f"no risk estimate for {missing}"
    sigma = None if problem or estimate is None else ex_ante_vol(held, estimate)
    if sigma is not None and sigma <= 0 and held:
        problem = "zero ex-ante volatility"
    diag_common: dict[str, Any] = {
        "session": base.session,
        "target_vol": settings.target_vol,
        "risk_fit_time": estimate.fit_time if estimate else None,
        "risk_window": (estimate.window_start, estimate.window_end) if estimate else None,
    }
    if not held:
        return base, VolTargetDiagnostics(
            **diag_common,
            ex_ante_vol_base=0.0,
            ex_ante_vol_final=0.0,
            raw_scale=None,
            applied_scale=0.0,
            capped=False,
            fallback_used=None,
        )
    if problem:
        if settings.fallback == "cash":
            weights: dict[str, float] = {}
            scale = 0.0
        else:
            weights, scale = dict(held), 1.0
        out = TargetWeights(
            session=base.session,
            method=f"vol_target({base.method})",
            weights=weights,
            cash_weight=1.0 - sum(weights.values()),
            cash_policy=base.cash_policy,
            notes=(*base.notes, f"fallback {settings.fallback}: {problem}"),
        )
        return out, VolTargetDiagnostics(
            **diag_common,
            ex_ante_vol_base=sigma,
            ex_ante_vol_final=None,
            raw_scale=None,
            applied_scale=scale,
            capped=False,
            fallback_used=f"{settings.fallback}: {problem}",
        )
    assert sigma is not None and estimate is not None
    raw = settings.target_vol / sigma
    scale = min(raw, settings.max_scale)
    gross = sum(abs(w) for w in held.values()) * scale
    if gross > settings.max_gross:
        scale *= settings.max_gross / gross
    capped = scale < raw - 1e-12
    weights = {a: w * scale for a, w in held.items()}
    out = TargetWeights(
        session=base.session,
        method=f"vol_target({base.method})",
        weights=weights,
        cash_weight=1.0 - sum(weights.values()),
        cash_policy=base.cash_policy,
        notes=base.notes + (("scale capped",) if capped else ()),
    )
    return out, VolTargetDiagnostics(
        **diag_common,
        ex_ante_vol_base=sigma,
        ex_ante_vol_final=ex_ante_vol(weights, estimate),
        raw_scale=raw,
        applied_scale=scale,
        capped=capped,
        fallback_used=None,
    )
