"""Gaussian-mixture regime baseline (Task 4.3)."""

from __future__ import annotations

import pytest

from fakes_regime import FEATURES, synthetic_frame
from macrosignal.domain.regime import ProbabilityType
from macrosignal.regimes.gmm import GmmConfig, fit_gmm, fit_gmm_candidates
from macrosignal.regimes.training import TrainingDataError

FRAME, STATES = synthetic_frame(160)
CUTOFF = FRAME.decision_times[99]


def _fit(k: int = 2, frame=FRAME, cutoff=CUTOFF):  # type: ignore[no-untyped-def]
    return fit_gmm(frame, GmmConfig(features=FEATURES, n_components=k, seed=1), cutoff, f"gmm_k{k}")


def test_fit_uses_training_window_only() -> None:
    fit = _fit()
    assert fit.n_train == 100 and fit.train_end == CUTOFF and fit.fit_cutoff == CUTOFF
    # Build a frame identical up to the cutoff but with different later rows.
    head = [c for c in FRAME.cells if c.as_of <= CUTOFF]
    tail = [c.model_copy(update={"value": c.value + 50}) for c in FRAME.cells if c.as_of > CUTOFF]
    altered = FRAME.model_copy(update={"cells": tuple(head + tail)})
    assert _fit(frame=altered).params_hash == fit.params_hash


def test_stores_components_and_occupancy() -> None:
    fit = _fit()
    assert len(fit.weights) == 2 and sum(fit.weights) == pytest.approx(1.0)
    assert sum(fit.occupancy) == pytest.approx(1.0)
    assert min(fit.occupancy) > 0.3
    growth_means = sorted(m[0] for m in fit.means_original)
    assert growth_means[0] == pytest.approx(-2.0, abs=0.3) and growth_means[1] == pytest.approx(
        2.0, abs=0.3
    )
    assert len(fit.covariances[0]) == 2 and fit.converged
    assert fit.config.seed == 1 and fit.scaler.features == FEATURES


def test_raw_posterior_is_unaligned_mixture_probability() -> None:
    fit = _fit()
    t = FRAME.decision_times[120]
    row = {c.feature_name: c.value for c in FRAME.row(t).values()}
    state = fit.posterior_state(t, row)
    assert state.probability_type is ProbabilityType.MIXTURE_POSTERIOR
    assert state.raw_probabilities is not None and max(state.raw_probabilities.values()) > 0.9
    assert not state.is_aligned
    with pytest.raises(TrainingDataError, match="does not impute"):
        fit.raw_probabilities({"growth": 1.0})


def test_deterministic_and_candidates() -> None:
    assert _fit().params_hash == _fit().params_hash
    fits = fit_gmm_candidates(FRAME, FEATURES, [2, 3, 4], CUTOFF, seed=1)
    assert [f.config.n_components for f in fits] == [2, 3, 4]
    assert all(f.fit_cutoff == CUTOFF for f in fits)
    assert fits[0].bic < fits[2].bic  # two true regimes


def test_insufficient_training_rows() -> None:
    with pytest.raises(TrainingDataError, match="complete training rows"):
        _fit(k=4, cutoff=FRAME.decision_times[5])
