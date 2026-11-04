"""Regime-based asset scores (Task 5.5)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from macrosignal.domain.regime import LiveStateError, RegimeObservation
from macrosignal.regimes.confidence import LowConfidencePolicy
from macrosignal.signals.regime_score import (
    RegimeAssetMap,
    TrainingRow,
    learn_regime_map,
    regime_scores,
)

NY = ZoneInfo("America/New_York")
T0 = datetime(2024, 1, 2, 9, 0, tzinfo=NY)
DECLARED = RegimeAssetMap(
    map_id="declared_v1",
    kind="declared",
    preferences={
        "growth_inflation": {"SPY": 1.0, "TLT": -1.0},
        "slowdown_disinflation": {"SPY": -1.0, "TLT": 1.0},
    },
)


def _state(p_growth: float, t: datetime = T0, **kw: Any) -> RegimeObservation:
    data: dict[str, Any] = {
        "as_of": t,
        "fit_id": "hmm_1",
        "model_version": "hmm-1",
        "fit_cutoff": T0 - timedelta(days=1),
        "probability_type": "filtered",
        "kind": "probability_vector",
        "raw_probabilities": {0: p_growth, 1: 1 - p_growth},
        "canonical_probabilities": {
            "growth_inflation": p_growth,
            "slowdown_disinflation": 1 - p_growth,
        },
        "alignment_confidence": 0.9,
    }
    data.update(kw)
    return RegimeObservation.model_validate(data)


def test_declared_map_scores_with_decomposition() -> None:
    s = regime_scores(_state(0.8), DECLARED, ["SPY", "TLT", "GLD"], LowConfidencePolicy())
    assert s["SPY"].raw_score == pytest.approx(0.6) and s["SPY"].confidence_weight == 1.0
    assert s["SPY"].decomposition == pytest.approx(
        {"growth_inflation": 0.8, "slowdown_disinflation": -0.2}
    )
    assert s["TLT"].score == pytest.approx(-0.6)
    assert s["GLD"].score == 0.0


def test_low_confidence_regime_contributes_nothing() -> None:
    s = regime_scores(_state(0.55), DECLARED, ["SPY"], LowConfidencePolicy(min_max_probability=0.6))
    assert s["SPY"].raw_score == pytest.approx(0.1) and s["SPY"].score == 0.0
    scaled = regime_scores(_state(0.9), DECLARED, ["SPY"], LowConfidencePolicy(action="scale"))
    assert 0 < scaled["SPY"].score < scaled["SPY"].raw_score


def test_only_live_aligned_states_accepted() -> None:
    with pytest.raises(LiveStateError):
        regime_scores(
            _state(0.8, canonical_probabilities=None, alignment_confidence=None),
            DECLARED,
            ["SPY"],
            LowConfidencePolicy(),
        )
    with pytest.raises(ValueError, match="no preferences"):
        regime_scores(
            _state(0.8, canonical_probabilities={"other": 0.8, "x": 0.2}),
            DECLARED,
            ["SPY"],
            LowConfidencePolicy(),
        )


def _rows(n: int) -> list[TrainingRow]:
    rows = []
    for i in range(n):
        t = T0 + timedelta(days=7 * i)
        growth = i % 2 == 0
        rows.append(
            TrainingRow(
                state=_state(0.9 if growth else 0.1, t=t),
                forward_end=t + timedelta(days=7),
                forward_returns={
                    "SPY": 0.01 if growth else -0.01,
                    "TLT": -0.005 if growth else 0.004,
                },
            )
        )
    return rows


def test_learned_map_uses_training_rows_only() -> None:
    rows = _rows(60)
    cutoff = rows[39].forward_end
    m = learn_regime_map(rows, cutoff, map_id="learned_v1", min_samples=5)
    assert m.preferences["growth_inflation"]["SPY"] == pytest.approx(0.01)
    assert m.preferences["slowdown_disinflation"]["TLT"] == pytest.approx(0.004)
    assert m.sample_counts["growth_inflation"]["SPY"] == 20
    later = [r.model_copy(update={"forward_returns": {"SPY": 9.0, "TLT": 9.0}}) for r in rows[40:]]
    assert learn_regime_map(rows[:40] + later, cutoff, map_id="learned_v1", min_samples=5) == m
    sparse = learn_regime_map(rows[:6], rows[5].forward_end, map_id="x", min_samples=5)
    assert sparse.preferences["growth_inflation"]["SPY"] == 0.0 and sparse.notes
    with pytest.raises(ValueError, match="after the decision time"):
        regime_scores(_state(0.8, t=cutoff - timedelta(days=30)), m, ["SPY"], LowConfidencePolicy())
