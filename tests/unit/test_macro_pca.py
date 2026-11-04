"""PCA macro-state baseline (Task 4.8)."""

from __future__ import annotations

import numpy as np
import pytest

from fakes_regime import FEATURES, synthetic_frame
from macrosignal.features.frame import SourceKind
from macrosignal.regimes.macro_pca import fit_macro_pca
from macrosignal.regimes.training import TrainingDataError

FRAME, _ = synthetic_frame(150)
CUTOFF = FRAME.decision_times[99]


def _fit(frame=FRAME, k: int = 2):  # type: ignore[no-untyped-def]
    return fit_macro_pca(frame, FEATURES, CUTOFF, n_components=k, fit_id="mpca")


def test_training_only_frozen_loadings() -> None:
    fit = _fit()
    assert fit.n_train == 100 and fit.fit_cutoff == CUTOFF
    head = [c for c in FRAME.cells if c.as_of <= CUTOFF]
    tail = [c.model_copy(update={"value": -c.value * 3}) for c in FRAME.cells if c.as_of > CUTOFF]
    assert (
        _fit(FRAME.model_copy(update={"cells": tuple(head + tail)})).params_hash == fit.params_hash
    )
    load = np.array(fit.loadings)
    assert np.allclose(load @ load.T, np.eye(2), atol=1e-10)
    assert all(row[np.argmax(np.abs(row))] > 0 for row in load)
    assert (
        fit.explained_variance_ratio[0] > 0.8
    )  # growth and inflation move together (opposite sign)


def test_factor_states_flag_in_sample_rows() -> None:
    fit = _fit(k=1)
    states = fit.factor_states(FRAME)
    assert len(states) == 150
    assert sum(s.in_sample for s in states) == 100
    assert all(len(s.scores) == 1 for s in states)
    a = {s.as_of: s.scores for s in states}
    b = {s.as_of: s.scores for s in _fit(k=1).factor_states(FRAME)}
    assert a == b


def test_only_macro_inputs_allowed() -> None:
    cells = tuple(
        c.model_copy(update={"kind": SourceKind.RATES}) if c.feature_name == "growth" else c
        for c in FRAME.cells
    )
    assert _fit(FRAME.model_copy(update={"cells": cells})).n_train == 100  # rates are macro inputs

    class FakeKind:  # anything outside macro/rates/curve kinds is refused
        value = "asset_return"

    bad = tuple(
        c.model_construct(**{**c.__dict__, "kind": FakeKind()}) if c.feature_name == "growth" else c
        for c in FRAME.cells
    )
    with pytest.raises(TrainingDataError, match="macro/rates features only"):
        _fit(FRAME.model_construct(**{**FRAME.__dict__, "cells": bad}))
    with pytest.raises(TrainingDataError, match="n_components"):
        _fit(k=3)
