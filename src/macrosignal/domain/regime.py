"""Regime state / probability data model.

A :class:`RegimeObservation` is one model's view of the regime at one decision
time.  It records the model fit id and version, the fit cutoff, the probability
type, and either a **hard label** (raw state id + canonical state id) or a
**probability vector** (raw state probabilities and, after alignment, canonical
state probabilities), plus the alignment confidence.

Integrity rules enforced at construction:

* probability vectors are non-negative and sum to one; canonical and raw
  vectors must have the same mass and number of states;
* a *future-informed* probability type (``smoothed``) can only be created with
  ``diagnostic=True`` - it can never pass as live state;
* a live (non-diagnostic) observation requires ``fit_cutoff <= as_of``;
* :func:`require_live_states` is the gate signal/backtest code must call: it
  rejects diagnostics, future-informed types and unaligned (no canonical id)
  states.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

CanonicalId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
PROBABILITY_TOLERANCE = 1e-6


class ProbabilityType(StrEnum):
    #: Rule-based or argmax hard assignment from contemporaneous information.
    HARD_RULE = "hard_rule"
    #: GMM posterior of the current observation under training-fitted parameters.
    MIXTURE_POSTERIOR = "mixture_posterior"
    #: HMM filtered probability P(s_t | x_1..x_t): contemporaneous.
    FILTERED = "filtered"
    #: HMM one-step prediction P(s_t | x_1..x_{t-1}): contemporaneous.
    PREDICTED = "predicted"
    #: HMM smoothed probability P(s_t | x_1..x_T): uses future data.
    SMOOTHED = "smoothed"


FUTURE_INFORMED = frozenset({ProbabilityType.SMOOTHED})


class StateKind(StrEnum):
    HARD_LABEL = "hard_label"
    PROBABILITY_VECTOR = "probability_vector"


class RegimeObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    fit_id: str
    model_version: str
    fit_cutoff: AwareDatetime
    probability_type: ProbabilityType
    kind: StateKind
    raw_state_id: int | None = None
    canonical_state_id: CanonicalId | None = None
    raw_probabilities: dict[int, float] | None = None
    canonical_probabilities: dict[CanonicalId, float] | None = None
    alignment_confidence: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    diagnostic: bool = False

    @model_validator(mode="after")
    def _check(self) -> RegimeObservation:
        problems: list[str] = []
        if self.probability_type in FUTURE_INFORMED and not self.diagnostic:
            problems.append(
                f"{self.probability_type.value} probabilities are future-informed and can only be "
                "created with diagnostic=True (ex-post use)"
            )
        if not self.diagnostic and self.fit_cutoff > self.as_of:
            problems.append("live state requires fit_cutoff <= as_of")
        if self.kind is StateKind.HARD_LABEL:
            if self.raw_probabilities is not None or self.canonical_probabilities is not None:
                problems.append("hard labels must not carry probability vectors")
            if self.raw_state_id is None and self.canonical_state_id is None:
                problems.append("hard label needs a raw or canonical state id")
        else:
            if self.raw_state_id is not None or self.canonical_state_id is not None:
                problems.append("probability vectors must not carry a hard state id")
            if self.raw_probabilities is None:
                problems.append("probability vector needs raw_probabilities")
            for name, vec in (
                ("raw", self.raw_probabilities),
                ("canonical", self.canonical_probabilities),
            ):
                if vec is None:
                    continue
                if any(p < 0 or not math.isfinite(p) for p in vec.values()):
                    problems.append(f"{name} probabilities must be finite and non-negative")
                if abs(sum(vec.values()) - 1.0) > PROBABILITY_TOLERANCE:
                    problems.append(f"{name} probabilities must sum to 1")
            if (
                self.raw_probabilities is not None
                and self.canonical_probabilities is not None
                and len(self.raw_probabilities) != len(self.canonical_probabilities)
            ):
                problems.append("raw and canonical vectors must have the same number of states")
        aligned = self.canonical_state_id is not None or self.canonical_probabilities is not None
        if aligned and self.probability_type is not ProbabilityType.HARD_RULE:
            if self.alignment_confidence is None:
                problems.append("aligned latent states need an alignment_confidence")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def is_aligned(self) -> bool:
        return self.canonical_state_id is not None or self.canonical_probabilities is not None

    @property
    def dominant_state(self) -> str | None:
        if self.canonical_state_id is not None:
            return self.canonical_state_id
        if self.canonical_probabilities:
            return max(self.canonical_probabilities.items(), key=lambda kv: (kv[1], kv[0]))[0]
        return None


class LiveStateError(ValueError):
    """A regime observation is not allowed in a live signal/backtest path."""


def require_live_states(states: Iterable[RegimeObservation]) -> list[RegimeObservation]:
    """Gate for signal/backtest consumers: contemporaneous, aligned, non-diagnostic only."""
    out: list[RegimeObservation] = []
    for s in states:
        if s.diagnostic:
            raise LiveStateError(f"{s.fit_id} @ {s.as_of.isoformat()}: diagnostic state")
        if s.probability_type in FUTURE_INFORMED:
            raise LiveStateError(f"{s.fit_id}: {s.probability_type.value} is future-informed")
        if not s.is_aligned:
            raise LiveStateError(
                f"{s.fit_id} @ {s.as_of.isoformat()}: raw states must be aligned to canonical ids"
            )
        out.append(s)
    return out
