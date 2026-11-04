"""Regime model / state-count selection policy (training data only).

For each candidate (model type x state count) fitted on the training window:

* **bic** - from the fit;
* **minimum occupancy** - smallest share of training rows assigned to a state;
* **persistence** - HMM: mean self-transition probability; GMM: share of
  consecutive training rows with the same most-likely component;
* **stability** - the same configuration refitted on the first
  ``stability_fraction`` of the training rows, aligned to the full fit
  (Hungarian matching, Task 4.6); the minimum alignment confidence, or 0 when
  the state count / alignment fails.

Selection rule (deterministic): keep candidates with occupancy >=
``min_occupancy``, persistence >= ``min_persistence`` and stability >=
``min_stability``; choose the lowest BIC; ties go to fewer states.  If none
qualifies, nothing is selected.  Only training-window macro features are ever
used - criteria that need returns or test-period performance (``sharpe``,
``returns``, ...) are refused - and **every** tested configuration is recorded in
the :class:`SelectionRegistry` with its metrics and whether it was selected.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.domain.manifest import stable_hash
from macrosignal.features.frame import AsOfFeatureFrame
from macrosignal.regimes.alignment import AlignmentStatus, CanonicalStateSet, align_states
from macrosignal.regimes.gmm import GmmConfig, GmmFit, fit_gmm
from macrosignal.regimes.hmm import HmmConfig, HmmFit, fit_hmm
from macrosignal.regimes.training import TrainingDataError, frame_rows

ALLOWED_CRITERIA = frozenset({"bic", "stability", "minimum_occupancy", "persistence"})
FORBIDDEN_HINTS = ("sharpe", "return", "pnl", "portfolio", "test")


class SelectionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    criteria: tuple[str, ...] = ("bic", "stability", "minimum_occupancy", "persistence")
    min_occupancy: float = Field(default=0.05, ge=0, le=1)
    min_persistence: float = Field(default=0.6, ge=0, le=1)
    min_stability: float = Field(default=0.3, ge=0, le=1)
    stability_fraction: float = Field(default=0.75, gt=0.2, lt=1)

    def model_post_init(self, __context: Any) -> None:
        bad = [c for c in self.criteria if c not in ALLOWED_CRITERIA]
        leaky = [c for c in self.criteria if any(h in c.lower() for h in FORBIDDEN_HINTS)]
        if leaky:
            raise ValueError(f"criteria {leaky} would select on returns / test performance")
        if bad:
            raise ValueError(f"unsupported selection criteria {bad}")


class TestedConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model_type: Literal["gmm", "hmm"]
    n_states: int
    seed: int
    features: tuple[str, ...]
    fit_cutoff: AwareDatetime
    fit_id: str
    bic: float
    min_occupancy: float
    persistence: float
    stability: float
    eligible: bool
    rejection_reasons: tuple[str, ...]
    selected: bool = False


class SelectionRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: SelectionPolicy
    tested: tuple[TestedConfiguration, ...]

    @property
    def selected(self) -> TestedConfiguration | None:
        return next((c for c in self.tested if c.selected), None)

    @property
    def n_variants(self) -> int:
        return len(self.tested)

    @property
    def registry_hash(self) -> str:
        return stable_hash(self)


def _fit(
    model_type: str,
    frame: AsOfFeatureFrame,
    features: Sequence[str],
    k: int,
    seed: int,
    cutoff: datetime,
    fit_id: str,
) -> GmmFit | HmmFit:
    if model_type == "gmm":
        return fit_gmm(
            frame, GmmConfig(features=tuple(features), n_components=k, seed=seed), cutoff, fit_id
        )
    return fit_hmm(
        frame, HmmConfig(features=tuple(features), n_states=k, seed=seed), cutoff, fit_id
    )


def _persistence(fit: GmmFit | HmmFit, frame: AsOfFeatureFrame) -> float:
    if isinstance(fit, HmmFit):
        return float(np.mean(np.diag(np.array(fit.transition))))
    times, x, _ = frame_rows(frame, fit.config.features, until=fit.fit_cutoff)
    labels = [
        max(
            p := fit.raw_probabilities(dict(zip(fit.config.features, row, strict=True))),
            key=p.__getitem__,
        )
        for row in x
    ]
    if len(labels) < 2:
        return 0.0
    return float(np.mean([a == b for a, b in zip(labels, labels[1:], strict=False)]))


def _stability(
    model_type: str,
    fit: GmmFit | HmmFit,
    frame: AsOfFeatureFrame,
    policy: SelectionPolicy,
    seed: int,
) -> float:
    times, _, _ = frame_rows(frame, fit.config.features, until=fit.fit_cutoff)
    early_cutoff = times[max(int(len(times) * policy.stability_fraction) - 1, 0)]
    k = len(fit.means_original)
    try:
        early = _fit(
            model_type, frame, fit.config.features, k, seed, early_cutoff, f"{fit.fit_id}_stability"
        )
    except TrainingDataError:
        return 0.0
    canonical = CanonicalStateSet(
        source_fit_id=fit.fit_id,
        features=fit.config.features,
        scales=fit.scaler.scales,
        descriptors={f"state_{i}": tuple(m) for i, m in enumerate(fit.means_original)},
    )
    res = align_states(early.fit_id, early.means_original, canonical, min_confidence=0.0)
    if res.status is AlignmentStatus.STATE_COUNT_CHANGED:
        return 0.0
    return res.min_confidence


def select_regime_model(
    frame: AsOfFeatureFrame,
    features: Sequence[str],
    cutoff: datetime,
    *,
    model_types: Sequence[Literal["gmm", "hmm"]],
    candidate_states: Sequence[int],
    policy: SelectionPolicy,
    seed: int = 0,
) -> SelectionRegistry:
    tested: list[TestedConfiguration] = []
    for model_type in model_types:
        for k in candidate_states:
            fit_id = f"{model_type}_k{k}_{cutoff:%Y%m%d}"
            fit = _fit(model_type, frame, features, k, seed, cutoff, fit_id)
            occ = float(min(fit.occupancy))
            pers = _persistence(fit, frame)
            stab = _stability(model_type, fit, frame, policy, seed)
            reasons = []
            if occ < policy.min_occupancy:
                reasons.append(f"min occupancy {occ:.3f} < {policy.min_occupancy}")
            if pers < policy.min_persistence:
                reasons.append(f"persistence {pers:.3f} < {policy.min_persistence}")
            if stab < policy.min_stability:
                reasons.append(f"stability {stab:.3f} < {policy.min_stability}")
            tested.append(
                TestedConfiguration(
                    model_type=model_type,
                    n_states=k,
                    seed=seed,
                    features=tuple(features),
                    fit_cutoff=cutoff,
                    fit_id=fit_id,
                    bic=fit.bic,
                    min_occupancy=occ,
                    persistence=pers,
                    stability=stab,
                    eligible=not reasons,
                    rejection_reasons=tuple(reasons),
                )
            )
    eligible = [c for c in tested if c.eligible]
    if eligible:
        best = min(eligible, key=lambda c: (c.bic, c.n_states, c.model_type))
        tested = [c.model_copy(update={"selected": c is best}) for c in tested]
    return SelectionRegistry(policy=policy, tested=tuple(tested))
