"""Gaussian HMM regime baseline (Task 4.4)."""

from __future__ import annotations

import numpy as np
import pytest

from fakes_regime import FEATURES, synthetic_frame
from macrosignal.domain.regime import LiveStateError, ProbabilityType, require_live_states
from macrosignal.regimes.hmm import HmmConfig, fit_hmm, fit_hmm_candidates

FRAME, STATES = synthetic_frame(180, block=20)
CUTOFF = FRAME.decision_times[119]


def _fit(k: int = 2, frame=FRAME):  # type: ignore[no-untyped-def]
    return fit_hmm(frame, HmmConfig(features=FEATURES, n_states=k, seed=3), CUTOFF, f"hmm_k{k}")


def test_fit_parameters_and_training_only() -> None:
    fit = _fit()
    a = np.array(fit.transition)
    assert a.shape == (2, 2) and np.allclose(a.sum(axis=1), 1.0)
    assert np.all(np.diag(a) > 0.85)  # persistent regimes
    assert fit.n_train == 120 and fit.train_end == CUTOFF and fit.config.seed == 3
    assert fit.converged and sum(fit.occupancy) == pytest.approx(1.0)
    # raw state 0 has the lower growth mean (deterministic ordering)
    assert fit.means_original[0][0] < fit.means_original[1][0]
    head = [c for c in FRAME.cells if c.as_of <= CUTOFF]
    tail = [c.model_copy(update={"value": c.value * 10}) for c in FRAME.cells if c.as_of > CUTOFF]
    assert (
        _fit(frame=FRAME.model_copy(update={"cells": tuple(head + tail)})).params_hash
        == fit.params_hash
    )
    assert _fit().params_hash == fit.params_hash  # deterministic


def test_filtered_probabilities_are_contemporaneous() -> None:
    fit = _fit()
    states = fit.filtered_states(FRAME)
    assert states and all(s.as_of > CUTOFF or s.as_of == CUTOFF for s in states)
    assert all(s.probability_type is ProbabilityType.FILTERED and not s.diagnostic for s in states)
    t = FRAME.decision_times[150]
    # Filtered value at t depends only on rows up to t: truncating later rows changes nothing.
    full = {s.as_of: s.raw_probabilities for s in states}
    trunc = {s.as_of: s.raw_probabilities for s in fit.filtered_states(FRAME, until=t)}
    assert trunc[t] == full[t]
    # accuracy against the true regime (raw 0 = slowdown centroid = synthetic state 1)
    hits = sum(
        (max(s.raw_probabilities, key=s.raw_probabilities.get) == 0) == (STATES[i] == 1)  # type: ignore[arg-type]
        for i, s in zip(range(120, 180), states, strict=False)
    )
    assert hits / len(states) > 0.9


def test_smoothed_are_diagnostic_and_future_informed() -> None:
    fit = _fit()
    smoothed = fit.smoothed_diagnostics(FRAME)
    assert all(s.diagnostic and s.probability_type is ProbabilityType.SMOOTHED for s in smoothed)
    with pytest.raises(LiveStateError):
        require_live_states(smoothed[:1])
    t = FRAME.decision_times[150]
    truncated = FRAME.model_copy(
        update={
            "cells": tuple(c for c in FRAME.cells if c.as_of <= t),
            "decision_times": tuple(x for x in FRAME.decision_times if x <= t),
        }
    )
    s_full = next(s for s in smoothed if s.as_of == FRAME.decision_times[140])
    s_trunc = next(
        s for s in fit.smoothed_diagnostics(truncated) if s.as_of == FRAME.decision_times[140]
    )
    assert s_full.raw_probabilities != s_trunc.raw_probabilities  # smoothing uses later data


def test_candidates_and_bic() -> None:
    fits = fit_hmm_candidates(FRAME, FEATURES, [2, 3], CUTOFF, seed=3)
    assert [len(f.transition) for f in fits] == [2, 3]
    assert fits[0].bic < fits[1].bic
