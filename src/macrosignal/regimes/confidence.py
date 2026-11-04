"""Regime probability uncertainty and the low-confidence policy.

Transparent measures per regime observation:

* ``max_probability`` - largest canonical (or raw) state probability;
* ``normalized_entropy`` - Shannon entropy divided by ``log(K)`` (0 = certain,
  1 = uniform);
* ``alignment_confidence`` - from state alignment (1.0 for rule-based labels);
* ``effective_confidence`` - ``sharpness * alignment_confidence`` where
  ``sharpness = (max_probability - 1/K) / (1 - 1/K)``.

:class:`LowConfidencePolicy` decides how a regime may influence signals:

* an observation is **low confidence** if ``max_probability < min_max_probability``,
  ``normalized_entropy > max_normalized_entropy`` or
  ``alignment_confidence < min_alignment_confidence``;
* ``action = "neutral"``: low-confidence regimes get ``signal_weight = 0``
  (no regime tilt), others ``1``;
* ``action = "scale"``: ``signal_weight = effective_confidence`` (0 when low
  confidence).

Neither action carries a previous regime forward or rounds probabilities up:
uncertainty only ever reduces the regime's influence.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.domain.regime import RegimeObservation, StateKind


class LowConfidencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_max_probability: float = Field(default=0.6, gt=0, le=1)
    max_normalized_entropy: float = Field(default=0.8, gt=0, le=1)
    min_alignment_confidence: float = Field(default=0.3, ge=0, le=1)
    action: Literal["neutral", "scale"] = "neutral"


class RegimeConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    fit_id: str
    dominant_state: str | None
    n_states: int
    max_probability: float
    normalized_entropy: float
    alignment_confidence: float
    effective_confidence: float
    low_confidence: bool
    reasons: tuple[str, ...]
    signal_weight: float = Field(ge=0.0, le=1.0)


def _probabilities(s: RegimeObservation) -> dict[Any, float]:
    if s.kind is StateKind.HARD_LABEL:
        return {s.canonical_state_id or s.raw_state_id: 1.0}
    return dict(s.canonical_probabilities or s.raw_probabilities or {})


def assess(s: RegimeObservation, policy: LowConfidencePolicy) -> RegimeConfidence:
    probs = _probabilities(s)
    k = max(len(probs), 1)
    pmax = max(probs.values()) if probs else 0.0
    entropy = -sum(p * math.log(p) for p in probs.values() if p > 0)
    norm_entropy = entropy / math.log(k) if k > 1 else 0.0
    if s.alignment_confidence is not None:
        align = s.alignment_confidence
    else:
        align = 1.0 if s.kind is StateKind.HARD_LABEL else 0.0
    sharpness = 1.0 if k == 1 else max(0.0, (pmax - 1 / k) / (1 - 1 / k))
    effective = sharpness * align
    reasons: list[str] = []
    if pmax < policy.min_max_probability:
        reasons.append(f"max_probability {pmax:.3f} < {policy.min_max_probability}")
    if norm_entropy > policy.max_normalized_entropy:
        reasons.append(f"normalized_entropy {norm_entropy:.3f} > {policy.max_normalized_entropy}")
    if align < policy.min_alignment_confidence:
        reasons.append(f"alignment_confidence {align:.3f} < {policy.min_alignment_confidence}")
    low = bool(reasons)
    if low:
        weight = 0.0
    else:
        weight = 1.0 if policy.action == "neutral" else float(min(max(effective, 0.0), 1.0))
    return RegimeConfidence(
        as_of=s.as_of,
        fit_id=s.fit_id,
        dominant_state=s.dominant_state,
        n_states=k,
        max_probability=pmax,
        normalized_entropy=norm_entropy,
        alignment_confidence=align,
        effective_confidence=effective,
        low_confidence=low,
        reasons=tuple(reasons),
        signal_weight=weight,
    )


def confidence_rows(
    states: Iterable[RegimeObservation], policy: LowConfidencePolicy
) -> list[dict[str, Any]]:
    """Flat rows for research outputs and the dashboard."""
    return [assess(s, policy).model_dump(mode="python") for s in states]
