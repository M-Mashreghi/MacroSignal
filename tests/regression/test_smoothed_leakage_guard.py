"""Filtered-vs-smoothed guard: deliberate leakage attempts must fail (Task 4.5)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fakes_regime import FEATURES, synthetic_frame
from macrosignal.domain.regime import LiveStateError, RegimeObservation
from macrosignal.regimes.guard import (
    ExPostDiagnostics,
    LiveRegimeSeries,
    live_regime_input,
    verify_filtered_against_fit,
)
from macrosignal.regimes.hmm import HmmConfig, fit_hmm

# Noisy regimes so smoothed and filtered probabilities genuinely differ.
FRAME, _ = synthetic_frame(160, block=20, noise=1.6)
CUTOFF = FRAME.decision_times[99]
FIT = fit_hmm(FRAME, HmmConfig(features=FEATURES, n_states=2, seed=3), CUTOFF, "hmm_guard")


def _align(s: RegimeObservation) -> RegimeObservation:
    """Stand-in for Task 4.6: map raw ids to canonical names with a confidence."""
    probs = s.raw_probabilities or {}
    return s.model_copy(
        update={
            "canonical_probabilities": {
                "slowdown_inflation": probs[0],
                "growth_disinflation": probs[1],
            },
            "alignment_confidence": 0.95,
        }
    )


@live_regime_input
def toy_signal(regimes: LiveRegimeSeries) -> int:
    return len(regimes)


def test_filtered_states_pass_the_guard() -> None:
    live = LiveRegimeSeries(_align(s) for s in FIT.filtered_states(FRAME))
    assert toy_signal(live) == len(live) > 0
    verify_filtered_against_fit(FIT, FRAME, live.states)


def test_leak_smoothed_diagnostics_into_signal_fails() -> None:
    smoothed = FIT.smoothed_diagnostics(FRAME)
    with pytest.raises(LiveStateError):
        LiveRegimeSeries(_align(s) for s in smoothed)
    with pytest.raises(LiveStateError, match="requires a LiveRegimeSeries"):
        toy_signal(ExPostDiagnostics(smoothed))  # type: ignore[arg-type]
    with pytest.raises(LiveStateError, match="requires a LiveRegimeSeries"):
        toy_signal(regimes=[_align(s) for s in FIT.filtered_states(FRAME)])  # type: ignore[arg-type]


def test_leak_by_dropping_diagnostic_flag_fails() -> None:
    smoothed = FIT.smoothed_diagnostics(FRAME)[120]
    with pytest.raises(ValidationError, match="future-informed"):
        RegimeObservation.model_validate({**smoothed.model_dump(), "diagnostic": False})


def test_leak_by_relabelling_smoothed_as_filtered_is_detected() -> None:
    smoothed = {s.as_of: s.raw_probabilities for s in FIT.smoothed_diagnostics(FRAME)}
    laundered = [
        _align(s.model_copy(update={"raw_probabilities": smoothed[s.as_of]}))
        for s in FIT.filtered_states(FRAME)
    ]
    live = LiveRegimeSeries(laundered)  # structurally valid...
    with pytest.raises(LiveStateError, match="possible smoothed-probability leakage"):
        verify_filtered_against_fit(FIT, FRAME, live.states)  # ...but caught on verification


def test_unaligned_or_out_of_order_states_fail() -> None:
    raw = FIT.filtered_states(FRAME)
    with pytest.raises(LiveStateError, match="aligned"):
        LiveRegimeSeries(raw)
    aligned = [_align(s) for s in raw]
    with pytest.raises(LiveStateError, match="strictly increasing"):
        LiveRegimeSeries(list(reversed(aligned)))
    with pytest.raises(ValueError, match="diagnostic or future-informed"):
        ExPostDiagnostics(aligned)
