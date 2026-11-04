"""Long / flat signal portfolio.

Translates combined scores into bounded long-only allocations:

* assets with ``score > min_score`` are long, all others flat (weight 0) -
  negative scores never create shorts;
* ``weighting = "proportional"`` sizes longs by score, ``"equal"`` gives each
  long the same weight;
* every weight is capped at ``max_weight`` and total long exposure at
  ``max_gross``; capped excess is **not** redistributed, it stays in cash;
* only assets tradable on the session can be held (scores for other assets are
  ignored with a note);
* unallocated capital is cash earning the declared :class:`CashReturnSpec`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from macrosignal.domain import CashReturnSpec
from macrosignal.portfolio.allocation import TargetWeights
from macrosignal.portfolio.universe import TradableUniverse


class LongFlatSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_score: float = 0.0
    weighting: Literal["proportional", "equal"] = "proportional"
    max_weight: float = Field(default=0.4, gt=0, le=1)
    max_gross: float = Field(default=1.0, gt=0, le=1)


def long_flat_weights(
    scores: Mapping[str, float],
    universe: TradableUniverse,
    settings: LongFlatSettings,
    cash_policy: CashReturnSpec,
) -> TargetWeights:
    notes: list[str] = []
    ignored = sorted(a for a in scores if a not in universe.assets)
    if ignored:
        notes.append(f"scores ignored for non-tradable assets {ignored}")
    longs = {a: s for a, s in scores.items() if a in universe.assets and s > settings.min_score}
    if not longs:
        return TargetWeights(
            session=universe.date,
            method="long_flat",
            weights={},
            cash_weight=1.0,
            cash_policy=cash_policy,
            notes=(*notes, "no positive scores; fully in cash"),
        )
    if settings.weighting == "equal":
        raw = {a: 1.0 for a in longs}
    else:
        raw = dict(longs)
    total = sum(raw.values())
    weights = {a: settings.max_gross * v / total for a, v in raw.items()}
    capped = {a: min(w, settings.max_weight) for a, w in weights.items()}
    if capped != weights:
        notes.append(f"weights capped at {settings.max_weight}; excess held in cash")
    cash = 1.0 - sum(capped.values())
    return TargetWeights(
        session=universe.date,
        method=f"long_flat:{settings.weighting}",
        weights=dict(sorted(capped.items())),
        cash_weight=cash,
        cash_policy=cash_policy,
        notes=tuple(notes),
    )
