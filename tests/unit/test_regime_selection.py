"""Regime model / state-count selection policy (Task 4.9)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fakes_regime import FEATURES, synthetic_frame
from macrosignal.regimes.selection import SelectionPolicy, select_regime_model

FRAME, _ = synthetic_frame(200, block=20)
CUTOFF = FRAME.decision_times[149]


def _select(**kw):  # type: ignore[no-untyped-def]
    args = {
        "model_types": ("gmm", "hmm"),
        "candidate_states": (2, 3),
        "policy": SelectionPolicy(),
        "seed": 2,
    }
    args.update(kw)
    return select_regime_model(FRAME, FEATURES, CUTOFF, **args)


def test_every_configuration_registered_and_one_selected() -> None:
    reg = _select()
    assert reg.n_variants == 4
    assert {(c.model_type, c.n_states) for c in reg.tested} == {
        ("gmm", 2),
        ("gmm", 3),
        ("hmm", 2),
        ("hmm", 3),
    }
    sel = reg.selected
    assert sel is not None and sel.n_states == 2
    assert sum(c.selected for c in reg.tested) == 1
    two_state = [c for c in reg.tested if c.n_states == 2]
    assert all(c.stability > 0.5 and c.persistence > 0.8 for c in two_state)
    assert all(c.fit_cutoff == CUTOFF for c in reg.tested)


def test_selection_is_training_only_and_deterministic() -> None:
    a = _select()
    head = [c for c in FRAME.cells if c.as_of <= CUTOFF]
    tail = [c.model_copy(update={"value": c.value * -5}) for c in FRAME.cells if c.as_of > CUTOFF]
    b = select_regime_model(
        FRAME.model_copy(update={"cells": tuple(head + tail)}),
        FEATURES,
        CUTOFF,
        model_types=("gmm", "hmm"),
        candidate_states=(2, 3),
        policy=SelectionPolicy(),
        seed=2,
    )
    assert a.registry_hash == b.registry_hash


def test_thresholds_can_reject_everything() -> None:
    reg = _select(policy=SelectionPolicy(min_occupancy=0.9))
    assert reg.selected is None
    assert all(not c.eligible and c.rejection_reasons for c in reg.tested)


@pytest.mark.parametrize("criterion", ["test_sharpe", "portfolio_return", "pnl"])
def test_return_based_criteria_refused(criterion: str) -> None:
    with pytest.raises(ValidationError, match="returns / test performance"):
        SelectionPolicy(criteria=("bic", criterion))
    with pytest.raises(ValidationError, match="unsupported"):
        SelectionPolicy(criteria=("aic",))
