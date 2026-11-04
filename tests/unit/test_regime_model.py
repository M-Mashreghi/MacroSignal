"""Regime state / probability data model (Task 4.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from macrosignal.domain.regime import (
    LiveStateError,
    ProbabilityType,
    RegimeObservation,
    StateKind,
    require_live_states,
)

NY = ZoneInfo("America/New_York")
T = datetime(2026, 6, 1, 9, 0, tzinfo=NY)


def _vec(**kw: Any) -> RegimeObservation:
    data: dict[str, Any] = {
        "as_of": T,
        "fit_id": "hmm_fit_2026_05",
        "model_version": "hmm-1",
        "fit_cutoff": T - timedelta(days=30),
        "probability_type": "filtered",
        "kind": "probability_vector",
        "raw_probabilities": {0: 0.7, 1: 0.3},
        "canonical_probabilities": {"growth_disinflation": 0.3, "slowdown_inflation": 0.7},
        "alignment_confidence": 0.9,
    }
    data.update(kw)
    return RegimeObservation.model_validate(data)


def test_probability_vector_and_hard_label() -> None:
    v = _vec()
    assert v.kind is StateKind.PROBABILITY_VECTOR and v.dominant_state == "slowdown_inflation"
    hard = RegimeObservation(
        as_of=T,
        fit_id="rule",
        model_version="quadrants-1",
        fit_cutoff=T,
        probability_type="hard_rule",
        kind="hard_label",
        canonical_state_id="growth_inflation",
    )
    assert hard.dominant_state == "growth_inflation" and hard.is_aligned
    assert require_live_states([v, hard]) == [v, hard]


@pytest.mark.parametrize(
    ("kw", "match"),
    [
        ({"raw_probabilities": {0: 0.7, 1: 0.4}}, "raw probabilities must sum to 1"),
        ({"raw_probabilities": {0: 1.2, 1: -0.2}}, "non-negative"),
        ({"canonical_probabilities": {"a": 1.0}}, "same number of states"),
        ({"raw_state_id": 1}, "must not carry a hard state id"),
        ({"raw_probabilities": None, "canonical_probabilities": None}, "needs raw_probabilities"),
        ({"alignment_confidence": None}, "alignment_confidence"),
        ({"alignment_confidence": 1.5}, "less than or equal"),
        ({"fit_cutoff": T + timedelta(days=1)}, "fit_cutoff <= as_of"),
    ],
)
def test_invalid_states_rejected(kw: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _vec(**kw)


def test_hard_label_rules() -> None:
    with pytest.raises(ValidationError, match="must not carry probability"):
        _vec(kind="hard_label", raw_state_id=0)
    with pytest.raises(ValidationError, match="needs a raw or canonical"):
        _vec(kind="hard_label", raw_probabilities=None, canonical_probabilities=None)


def test_smoothed_cannot_be_live() -> None:
    with pytest.raises(ValidationError, match="future-informed"):
        _vec(probability_type="smoothed")
    diag = _vec(probability_type="smoothed", diagnostic=True, fit_cutoff=T + timedelta(days=90))
    assert diag.probability_type is ProbabilityType.SMOOTHED
    with pytest.raises(LiveStateError, match="diagnostic"):
        require_live_states([diag])


def test_unaligned_raw_states_blocked_from_live_use() -> None:
    raw_only = _vec(canonical_probabilities=None, alignment_confidence=None)
    assert not raw_only.is_aligned and raw_only.dominant_state is None
    with pytest.raises(LiveStateError, match="aligned"):
        require_live_states([raw_only])
    diag_filtered = _vec(diagnostic=True)
    with pytest.raises(LiveStateError):
        require_live_states([diag_filtered])
