"""Latent state canonicalization / alignment across refits.

Raw GMM/HMM state indices are arbitrary.  After each refit the new states'
macro descriptors (state means in original feature units) are matched to the
prior canonical descriptors with a deterministic one-to-one minimum-cost
assignment (Hungarian algorithm, ``scipy.optimize.linear_sum_assignment``) on
scale-normalized Euclidean distance.

Each mapping stores its distance and a confidence ``1 - d_assigned /
d_second_best`` (how much better the chosen canonical state fits than the
runner-up).  A mapping is *ambiguous* when its confidence is below
``min_confidence`` or its distance above ``max_distance``.  A different number
of states is never forced into a map: the result has status
``state_count_changed`` and cannot be applied.

The first canonical set is bootstrapped from the transparent quadrant semantics
of each state's standardized growth / inflation means
(:func:`bootstrap_canonical`); later sets roll forward from the aligned fit.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.optimize import linear_sum_assignment  # type: ignore[import-untyped]

from macrosignal.domain.regime import RegimeObservation, StateKind
from macrosignal.regimes.quadrants import classify


class CanonicalStateSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_fit_id: str
    features: tuple[str, ...]
    scales: tuple[float, ...]
    descriptors: dict[str, tuple[float, ...]]  # canonical id -> centroid (original units)


class AlignmentStatus(StrEnum):
    OK = "ok"
    AMBIGUOUS = "ambiguous"
    STATE_COUNT_CHANGED = "state_count_changed"


class StateMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_state_id: int
    canonical_state_id: str
    matching_distance: float
    alignment_confidence: float = Field(ge=0.0, le=1.0)
    ambiguous: bool


class AlignmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_id: str
    prior_fit_id: str
    status: AlignmentStatus
    mappings: tuple[StateMapping, ...]
    detail: str = ""

    @property
    def raw_to_canonical(self) -> dict[int, str]:
        return {m.raw_state_id: m.canonical_state_id for m in self.mappings}

    @property
    def min_confidence(self) -> float:
        return min((m.alignment_confidence for m in self.mappings), default=0.0)


class AlignmentError(ValueError):
    """An alignment cannot be applied (ambiguous or state count changed)."""


def bootstrap_canonical(
    fit_id: str,
    features: Sequence[str],
    means_original: Sequence[Sequence[float]],
    means_std: Sequence[Sequence[float]],
    scales: Sequence[float],
    *,
    growth_index: int = 0,
    inflation_index: int = 1,
) -> CanonicalStateSet:
    """Name each state by the quadrant of its standardized (growth, inflation) mean."""
    names: dict[str, tuple[float, ...]] = {}
    for mean_std, mean_orig in zip(means_std, means_original, strict=True):
        name = classify(mean_std[growth_index], mean_std[inflation_index], 0.0, 0.0).value
        if name in names:
            raise AlignmentError(
                f"two states of {fit_id} fall in the same quadrant ({name}); bootstrap needs an "
                "explicit canonical definition"
            )
        names[name] = tuple(float(v) for v in mean_orig)
    return CanonicalStateSet(
        source_fit_id=fit_id,
        features=tuple(features),
        scales=tuple(float(s) for s in scales),
        descriptors=names,
    )


def align_states(
    fit_id: str,
    means_original: Sequence[Sequence[float]],
    canonical: CanonicalStateSet,
    *,
    min_confidence: float = 0.3,
    max_distance: float | None = None,
) -> AlignmentResult:
    new = np.asarray(means_original, dtype=float)
    names = sorted(canonical.descriptors)
    if new.shape[0] != len(names):
        return AlignmentResult(
            fit_id=fit_id,
            prior_fit_id=canonical.source_fit_id,
            status=AlignmentStatus.STATE_COUNT_CHANGED,
            mappings=(),
            detail=(
                f"{new.shape[0]} new states vs {len(names)} canonical states; "
                "explicit policy needed"
            ),
        )
    if new.shape[1] != len(canonical.features):
        raise AlignmentError("descriptor dimension does not match the canonical features")
    ref = np.array([canonical.descriptors[n] for n in names])
    scales = np.array(canonical.scales)
    dist = np.linalg.norm((new[:, None, :] - ref[None, :, :]) / scales, axis=2)
    rows, cols = linear_sum_assignment(dist)
    mappings: list[StateMapping] = []
    for r, c in sorted(zip(rows, cols, strict=True)):
        d1 = float(dist[r, c])
        others = np.delete(dist[r], c)
        d2 = float(others.min()) if others.size else float("inf")
        conf = 1.0 if d2 == float("inf") else (1.0 - d1 / d2 if d2 > 0 else 0.0)
        conf = float(min(max(conf, 0.0), 1.0))
        ambiguous = conf < min_confidence or (max_distance is not None and d1 > max_distance)
        mappings.append(
            StateMapping(
                raw_state_id=int(r),
                canonical_state_id=names[c],
                matching_distance=d1,
                alignment_confidence=conf,
                ambiguous=ambiguous,
            )
        )
    status = AlignmentStatus.AMBIGUOUS if any(m.ambiguous for m in mappings) else AlignmentStatus.OK
    return AlignmentResult(
        fit_id=fit_id, prior_fit_id=canonical.source_fit_id, status=status, mappings=tuple(mappings)
    )


def apply_alignment(
    states: Sequence[RegimeObservation], alignment: AlignmentResult
) -> list[RegimeObservation]:
    """Attach canonical probabilities / ids; refuses non-OK alignments."""
    if alignment.status is not AlignmentStatus.OK:
        raise AlignmentError(f"alignment of {alignment.fit_id} is {alignment.status.value}")
    mapping = alignment.raw_to_canonical
    out: list[RegimeObservation] = []
    for s in states:
        if s.fit_id != alignment.fit_id:
            raise AlignmentError(
                f"state from {s.fit_id} cannot use alignment of {alignment.fit_id}"
            )
        if s.kind is StateKind.HARD_LABEL:
            assert s.raw_state_id is not None
            update: dict[str, Any] = {"canonical_state_id": mapping[s.raw_state_id]}
        else:
            raw = s.raw_probabilities or {}
            update = {"canonical_probabilities": {mapping[k]: v for k, v in raw.items()}}
        out.append(
            RegimeObservation.model_validate(
                {**s.model_dump(), **update, "alignment_confidence": alignment.min_confidence}
            )
        )
    return out


def roll_forward(
    canonical: CanonicalStateSet,
    alignment: AlignmentResult,
    means_original: Sequence[Sequence[float]],
) -> CanonicalStateSet:
    """Canonical descriptors for the next refit, taken from the newly aligned fit."""
    if alignment.status is not AlignmentStatus.OK:
        raise AlignmentError("only an OK alignment can update canonical descriptors")
    desc = {
        m.canonical_state_id: tuple(float(v) for v in means_original[m.raw_state_id])
        for m in alignment.mappings
    }
    return canonical.model_copy(update={"source_fit_id": alignment.fit_id, "descriptors": desc})
