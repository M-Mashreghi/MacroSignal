"""Regime-based per-asset scores from aligned canonical regime probabilities.

``score_a(t) = w(t) * sum_s P_t(s) * M[s, a]``

* ``P_t`` - canonical regime probabilities (or a hard canonical label) of a
  **live** regime observation (aligned, contemporaneous, non-diagnostic);
* ``M`` - a :class:`RegimeAssetMap`: either *declared* (a-priori preferences,
  e.g. +1 equities / -1 duration in ``growth_inflation``) or *learned* by
  :func:`learn_regime_map` as the mean forward return of each asset in periods
  dominated by each regime, using only observations whose forward return was
  complete by the training cutoff (minimum sample per cell, otherwise 0 with a
  note);
* ``w(t)`` - the regime confidence weight from the low-confidence policy
  (Task 4.7); low-confidence regimes contribute nothing.

Every score carries its decomposition by regime (``P(s) * M[s, a]``) and the
confidence weight applied.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.domain.regime import RegimeObservation, StateKind, require_live_states
from macrosignal.regimes.confidence import LowConfidencePolicy, assess


class RegimeAssetMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    map_id: str
    kind: Literal["declared", "learned"]
    preferences: dict[str, dict[str, float]]  # regime -> asset -> preference
    fit_cutoff: AwareDatetime | None = None
    sample_counts: dict[str, dict[str, int]] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @property
    def assets(self) -> list[str]:
        return sorted({a for row in self.preferences.values() for a in row})


class TrainingRow(BaseModel):
    """A live regime state with the asset returns realised *after* it (forward window)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: RegimeObservation
    forward_end: AwareDatetime
    forward_returns: dict[str, float]


def learn_regime_map(
    rows: Sequence[TrainingRow],
    cutoff: datetime,
    *,
    map_id: str,
    min_samples: int = 10,
) -> RegimeAssetMap:
    """Mean forward return per (dominant regime, asset) on training rows only."""
    live = require_live_states([r.state for r in rows])
    sums: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row, state in zip(rows, live, strict=True):
        if row.forward_end > cutoff or state.as_of > cutoff:
            continue  # forward window not complete by the training cutoff
        regime = state.dominant_state
        assert regime is not None
        for asset, ret in row.forward_returns.items():
            sums[regime][asset] += ret
            counts[regime][asset] += 1
    prefs: dict[str, dict[str, float]] = {}
    notes: list[str] = []
    for regime in sorted(counts):
        prefs[regime] = {}
        for asset in sorted(counts[regime]):
            n = counts[regime][asset]
            if n < min_samples:
                prefs[regime][asset] = 0.0
                notes.append(f"{regime}/{asset}: {n} samples < {min_samples}; preference set to 0")
            else:
                prefs[regime][asset] = sums[regime][asset] / n
    return RegimeAssetMap(
        map_id=map_id,
        kind="learned",
        preferences=prefs,
        fit_cutoff=cutoff,
        sample_counts={k: dict(v) for k, v in counts.items()},
        notes=tuple(notes),
    )


class RegimeAssetScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    asset_id: str
    score: float
    raw_score: float
    confidence_weight: float
    decomposition: dict[str, float]
    map_id: str
    regime_fit_id: str


def regime_scores(
    state: RegimeObservation,
    mapping: RegimeAssetMap,
    assets: Sequence[str],
    policy: LowConfidencePolicy,
) -> dict[str, RegimeAssetScore]:
    (live,) = require_live_states([state])
    if mapping.fit_cutoff is not None and mapping.fit_cutoff > live.as_of:
        raise ValueError("a learned map fitted after the decision time cannot be used")
    if live.kind is StateKind.HARD_LABEL:
        assert live.canonical_state_id is not None
        probs: Mapping[str, float] = {live.canonical_state_id: 1.0}
    else:
        probs = live.canonical_probabilities or {}
    unknown = sorted(set(probs) - set(mapping.preferences))
    if unknown:
        raise ValueError(f"regime map {mapping.map_id} has no preferences for {unknown}")
    weight = assess(live, policy).signal_weight
    out: dict[str, RegimeAssetScore] = {}
    for asset in assets:
        parts = {s: p * mapping.preferences[s].get(asset, 0.0) for s, p in probs.items()}
        raw = sum(parts.values())
        out[asset] = RegimeAssetScore(
            as_of=live.as_of,
            asset_id=asset,
            score=weight * raw,
            raw_score=raw,
            confidence_weight=weight,
            decomposition=parts,
            map_id=mapping.map_id,
            regime_fit_id=live.fit_id,
        )
    return out
