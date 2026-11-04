"""Regime uncertainty and low-confidence policy (Task 4.7)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from macrosignal.domain.regime import RegimeObservation
from macrosignal.regimes.confidence import LowConfidencePolicy, assess, confidence_rows

NY = ZoneInfo("America/New_York")
T = datetime(2026, 6, 1, 9, 0, tzinfo=NY)


def _vec(p: float, align: float = 0.9, k3: bool = False) -> RegimeObservation:
    probs: dict[str, float] = {"growth_disinflation": p, "slowdown_inflation": 1 - p}
    raw: dict[int, float] = {0: p, 1: 1 - p}
    if k3:
        probs = {"a": p, "b": (1 - p) / 2, "c": (1 - p) / 2}
        raw = {0: p, 1: (1 - p) / 2, 2: (1 - p) / 2}
    data: dict[str, Any] = {
        "as_of": T,
        "fit_id": "f",
        "model_version": "hmm-1",
        "fit_cutoff": T - timedelta(days=1),
        "probability_type": "filtered",
        "kind": "probability_vector",
        "raw_probabilities": raw,
        "canonical_probabilities": probs,
        "alignment_confidence": align,
    }
    return RegimeObservation.model_validate(data)


def test_measures() -> None:
    c = assess(_vec(0.9), LowConfidencePolicy())
    assert c.max_probability == 0.9 and c.dominant_state == "growth_disinflation"
    h = -(0.9 * math.log(0.9) + 0.1 * math.log(0.1)) / math.log(2)
    assert c.normalized_entropy == pytest.approx(h)
    assert c.effective_confidence == pytest.approx(0.8 * 0.9)
    assert not c.low_confidence and c.signal_weight == 1.0
    uniform = assess(_vec(1 / 3, k3=True), LowConfidencePolicy())
    assert uniform.normalized_entropy == pytest.approx(
        1.0
    ) and uniform.effective_confidence == pytest.approx(0, abs=1e-12)


def test_low_confidence_never_invents_certainty() -> None:
    policy = LowConfidencePolicy(min_max_probability=0.6, action="neutral")
    c = assess(_vec(0.55), policy)
    assert c.low_confidence and c.signal_weight == 0.0 and "max_probability" in c.reasons[0]
    misaligned = assess(_vec(0.95, align=0.1), policy)
    assert misaligned.low_confidence and any("alignment" in r for r in misaligned.reasons)


def test_scale_action_shrinks_weight() -> None:
    policy = LowConfidencePolicy(action="scale")
    strong, mild = assess(_vec(0.95), policy), assess(_vec(0.8), policy)
    assert 0 < mild.signal_weight < strong.signal_weight < 1
    assert assess(_vec(0.5), policy).signal_weight == 0.0


def test_hard_rule_label_and_unaligned_raw() -> None:
    hard = RegimeObservation(
        as_of=T,
        fit_id="rule",
        model_version="q",
        fit_cutoff=T,
        probability_type="hard_rule",
        kind="hard_label",
        canonical_state_id="growth_inflation",
    )
    c = assess(hard, LowConfidencePolicy())
    assert c.max_probability == 1.0 and c.signal_weight == 1.0 and c.alignment_confidence == 1.0
    raw = _vec(0.9).model_copy(
        update={"canonical_probabilities": None, "alignment_confidence": None}
    )
    assert assess(raw, LowConfidencePolicy()).low_confidence  # unaligned -> no confidence


def test_rows_for_outputs() -> None:
    rows = confidence_rows([_vec(0.9), _vec(0.55)], LowConfidencePolicy())
    assert [r["low_confidence"] for r in rows] == [False, True]
    assert {"normalized_entropy", "signal_weight", "reasons"} <= set(rows[0])
