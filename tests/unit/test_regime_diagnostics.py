"""Regime persistence / transition / alignment diagnostics (Task 4.10)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from macrosignal.domain.regime import RegimeObservation
from macrosignal.regimes.alignment import AlignmentResult, AlignmentStatus, StateMapping
from macrosignal.regimes.diagnostics import DiagnosticThresholds, regime_diagnostics

NY = ZoneInfo("America/New_York")
T0 = datetime(2026, 1, 5, 9, 0, tzinfo=NY)


def _states(labels: list[str | None]) -> list[RegimeObservation]:
    out = []
    for i, lab in enumerate(labels):
        t = T0 + timedelta(days=7 * i)
        if lab is None:
            out.append(
                RegimeObservation(
                    as_of=t,
                    fit_id="f",
                    model_version="m",
                    fit_cutoff=T0,
                    probability_type="filtered",
                    kind="probability_vector",
                    raw_probabilities={0: 0.5, 1: 0.5},
                )
            )
        else:
            out.append(
                RegimeObservation(
                    as_of=t,
                    fit_id="f",
                    model_version="m",
                    fit_cutoff=T0,
                    probability_type="hard_rule",
                    kind="hard_label",
                    canonical_state_id=lab,
                )
            )
    return out


def _alignment(conf: float, status: AlignmentStatus = AlignmentStatus.OK) -> AlignmentResult:
    maps = (
        ()
        if status is AlignmentStatus.STATE_COUNT_CHANGED
        else (
            StateMapping(
                raw_state_id=0,
                canonical_state_id="a",
                matching_distance=0.1,
                alignment_confidence=conf,
                ambiguous=conf < 0.3,
            ),
            StateMapping(
                raw_state_id=1,
                canonical_state_id="b",
                matching_distance=0.2,
                alignment_confidence=0.9,
                ambiguous=False,
            ),
        )
    )
    return AlignmentResult(fit_id="x", prior_fit_id="y", status=status, mappings=maps)


def test_durations_occupancy_transitions() -> None:
    d = regime_diagnostics(_states(["a", "a", "a", "b", "b", "a", "a", "c", None]))
    by = {s.state: s for s in d.states}
    assert d.n_observations == 9 and d.n_unassigned == 1
    assert by["a"].occupancy == pytest.approx(5 / 8) and by["a"].n_spells == 2
    assert by["a"].mean_duration == pytest.approx(2.5) and by["a"].max_duration == 3
    assert by["c"].mean_duration == 1 and by["c"].unstable
    assert d.transition_matrix["a"] == pytest.approx({"a": 3 / 5, "b": 1 / 5, "c": 1 / 5})
    assert d.transition_matrix["b"] == pytest.approx({"b": 0.5, "a": 0.5})


def test_rare_and_weakly_aligned_flags_and_stability() -> None:
    labels = ["a"] * 30 + ["b"]
    al = [
        _alignment(0.8),
        _alignment(0.2, AlignmentStatus.AMBIGUOUS),
        _alignment(0, AlignmentStatus.STATE_COUNT_CHANGED),
    ]
    d = regime_diagnostics(_states(labels), al, DiagnosticThresholds(min_occupancy=0.1))
    by = {s.state: s for s in d.states}
    assert by["b"].rare and by["a"].weakly_aligned
    assert set(d.flagged_states) == {"a", "b"}
    st = d.refit_stability
    assert (st.n_refits, st.n_ok, st.n_ambiguous, st.n_state_count_changed) == (3, 1, 1, 1)
    assert st.min_confidence == pytest.approx(0.2)


def test_report_artifacts() -> None:
    d = regime_diagnostics(_states(["a", "b", "a"]), [_alignment(0.7)])
    tables = d.report_tables()
    assert {"states", "transitions", "refit_stability"} == set(tables)
    assert json.loads(d.to_canonical_json())["n_observations"] == 3
    assert (
        d.to_canonical_json()
        == regime_diagnostics(_states(["a", "b", "a"]), [_alignment(0.7)]).to_canonical_json()
    )
