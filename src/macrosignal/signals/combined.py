"""Combined transparent signal: regime + decayed surprise + optional trend.

``total_a = w_regime * regime_a + w_surprise * surprise_a + w_trend * trend_a``

with each component's score exposed in the decomposition (``trend_a`` is the
guardrail direction, 0 when missing or disabled).  Weights are either declared
or chosen by :func:`select_weights` from a declared candidate grid using only
training / validation rows whose forward returns were complete by the selection
cutoff; the selection metric is the mean of ``total_a x forward_return_a``
across rows and assets.  Every evaluated candidate is recorded with its metric.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.domain.manifest import canonical_json
from macrosignal.signals.regime_score import RegimeAssetScore
from macrosignal.signals.surprise_score import SurpriseAssetScore
from macrosignal.signals.trend import TrendSignal, TrendStatus


class ComponentWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    regime: float = Field(ge=0)
    surprise: float = Field(ge=0)
    trend: float = Field(ge=0)


class WeightSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    selected: ComponentWeights
    method: str
    selection_cutoff: AwareDatetime | None
    n_rows_used: int
    candidates: tuple[tuple[ComponentWeights, float], ...]


class CombinedScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    asset_id: str
    total: float
    components: dict[str, float]
    weighted: dict[str, float]
    weights: ComponentWeights
    missing_components: tuple[str, ...]


def combine(
    as_of: datetime,
    assets: Sequence[str],
    weights: ComponentWeights,
    regime: Mapping[str, RegimeAssetScore] | None = None,
    surprise: Mapping[str, SurpriseAssetScore] | None = None,
    trend: Mapping[str, TrendSignal] | None = None,
) -> dict[str, CombinedScore]:
    out: dict[str, CombinedScore] = {}
    for asset in assets:
        comps: dict[str, float] = {}
        missing: list[str] = []
        r = (regime or {}).get(asset)
        if r is None:
            missing.append("regime")
        comps["regime"] = r.score if r else 0.0
        s = (surprise or {}).get(asset)
        if s is None:
            missing.append("surprise")
        comps["surprise"] = s.score if s else 0.0
        t = (trend or {}).get(asset)
        if t is None or t.status is not TrendStatus.OK:
            missing.append("trend")
        comps["trend"] = float(t.direction) if t and t.direction is not None else 0.0
        weighted = {
            "regime": weights.regime * comps["regime"],
            "surprise": weights.surprise * comps["surprise"],
            "trend": weights.trend * comps["trend"],
        }
        out[asset] = CombinedScore(
            as_of=as_of,
            asset_id=asset,
            total=sum(weighted.values()),
            components=comps,
            weighted=weighted,
            weights=weights,
            missing_components=tuple(missing),
        )
    return out


class SelectionRow(BaseModel):
    """Component scores at one decision time with the forward returns that followed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    forward_end: AwareDatetime
    components: dict[str, dict[str, float]]  # asset -> component -> score
    forward_returns: dict[str, float]


def select_weights(
    rows: Sequence[SelectionRow],
    candidates: Sequence[ComponentWeights],
    cutoff: datetime,
) -> WeightSelection:
    if not candidates:
        raise ValueError("at least one candidate weighting is required")
    usable = [r for r in rows if r.forward_end <= cutoff]
    if not usable:
        raise ValueError("no training/validation rows completed before the selection cutoff")
    results: list[tuple[ComponentWeights, float]] = []
    for w in candidates:
        vals = []
        for row in usable:
            for asset, comps in row.components.items():
                if asset not in row.forward_returns:
                    continue
                total = (
                    w.regime * comps.get("regime", 0.0)
                    + w.surprise * comps.get("surprise", 0.0)
                    + w.trend * comps.get("trend", 0.0)
                )
                vals.append(total * row.forward_returns[asset])
        results.append((w, sum(vals) / len(vals) if vals else 0.0))
    best = max(results, key=lambda wm: (wm[1], -wm[0].regime - wm[0].surprise - wm[0].trend))[0]
    return WeightSelection(
        selected=best,
        method="mean_score_times_forward_return",
        selection_cutoff=cutoff,
        n_rows_used=len(usable),
        candidates=tuple(results),
    )


def decomposition_rows(scores: Mapping[str, CombinedScore]) -> list[dict[str, Any]]:
    """Per-asset decomposition artifact rows."""
    rows = []
    for asset, s in sorted(scores.items()):
        rows.append(
            {
                "as_of": s.as_of,
                "asset_id": asset,
                "total": s.total,
                **{f"{k}_score": v for k, v in s.components.items()},
                **{f"{k}_weighted": v for k, v in s.weighted.items()},
                "missing_components": list(s.missing_components),
            }
        )
    return rows


def decomposition_json(scores: Mapping[str, CombinedScore]) -> str:
    return canonical_json(decomposition_rows(scores))
