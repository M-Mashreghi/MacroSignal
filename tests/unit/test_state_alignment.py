"""Latent state canonicalization / alignment (Task 4.6)."""

from __future__ import annotations

import pytest

from fakes_regime import FEATURES, synthetic_frame
from macrosignal.domain.regime import require_live_states
from macrosignal.fixtures import load_state_alignment_fixture
from macrosignal.regimes.alignment import (
    AlignmentError,
    AlignmentStatus,
    CanonicalStateSet,
    align_states,
    apply_alignment,
    bootstrap_canonical,
    roll_forward,
)
from macrosignal.regimes.hmm import HmmConfig, fit_hmm


def _fixture_sets() -> tuple[CanonicalStateSet, list[tuple[float, float]]]:
    rows = load_state_alignment_fixture()
    a = {r.raw_state_id: r for r in rows if r.fit_id == "fit_A"}
    canonical = CanonicalStateSet(
        source_fit_id="fit_A",
        features=("growth", "inflation"),
        scales=(1.0, 1.0),
        descriptors={
            a[i].prior_canonical_state: (a[i].growth_factor, a[i].inflation_factor)  # type: ignore[misc]
            for i in a
        },
    )
    b = sorted((r for r in rows if r.fit_id == "fit_B"), key=lambda r: r.raw_state_id)
    return canonical, [(r.growth_factor, r.inflation_factor) for r in b]


def test_permuted_raw_ids_are_realigned() -> None:
    canonical, fit_b = _fixture_sets()
    res = align_states("fit_B", fit_b, canonical)
    assert res.status is AlignmentStatus.OK
    # fit_B raw 0 = (-1.0, 0.9) is the slowdown/inflation state; raw 1 is growth/disinflation.
    assert res.raw_to_canonical == {0: "slowdown_inflation", 1: "growth_disinflation"}
    assert all(m.alignment_confidence > 0.8 for m in res.mappings)
    assert res.prior_fit_id == "fit_A"


def test_matching_is_deterministic_one_to_one() -> None:
    canonical, fit_b = _fixture_sets()
    a, b = align_states("fit_B", fit_b, canonical), align_states("fit_B", fit_b, canonical)
    assert a == b
    assert len(set(a.raw_to_canonical.values())) == len(a.mappings)


def test_ambiguous_and_state_count_changes_flagged() -> None:
    canonical, _ = _fixture_sets()
    mid = align_states("fit_C", [(0.05, 0.0), (0.0, 0.05)], canonical)
    assert mid.status is AlignmentStatus.AMBIGUOUS and any(m.ambiguous for m in mid.mappings)
    far = align_states("fit_D", [(9.0, -9.0), (-9.0, 9.0)], canonical, max_distance=3.0)
    assert far.status is AlignmentStatus.AMBIGUOUS
    three = align_states("fit_E", [(1, -1), (-1, 1), (0, 0)], canonical)
    assert three.status is AlignmentStatus.STATE_COUNT_CHANGED and three.mappings == ()
    with pytest.raises(AlignmentError, match="state_count_changed"):
        apply_alignment([], three)


def test_refit_on_swapped_data_aligns_and_feeds_live_states() -> None:
    frame_a, _ = synthetic_frame(160, block=20, seed=11)
    fit_a = fit_hmm(
        frame_a,
        HmmConfig(features=FEATURES, n_states=2, seed=1),
        frame_a.decision_times[99],
        "hmm_A",
    )
    canonical = bootstrap_canonical(
        fit_a.fit_id, FEATURES, fit_a.means_original, fit_a.means_std, fit_a.scaler.scales
    )
    assert set(canonical.descriptors) == {"growth_disinflation", "slowdown_inflation"}
    frame_b, _ = synthetic_frame(160, block=20, seed=12)
    fit_b = fit_hmm(
        frame_b,
        HmmConfig(features=FEATURES, n_states=2, seed=5),
        frame_b.decision_times[109],
        "hmm_B",
    )
    res = align_states(fit_b.fit_id, fit_b.means_original, canonical)
    assert res.status is AlignmentStatus.OK
    aligned = apply_alignment(fit_b.filtered_states(frame_b), res)
    live = require_live_states(aligned)
    assert all(s.canonical_probabilities and s.alignment_confidence for s in live)
    growth_raw = max(range(2), key=lambda i: fit_b.means_original[i][0])
    assert res.raw_to_canonical[growth_raw] == "growth_disinflation"
    nxt = roll_forward(canonical, res, fit_b.means_original)
    assert nxt.source_fit_id == "hmm_B"
    with pytest.raises(AlignmentError, match="cannot use alignment"):
        apply_alignment(fit_a.filtered_states(frame_a)[:1], res)


def test_bootstrap_rejects_duplicate_quadrants() -> None:
    with pytest.raises(AlignmentError, match="same quadrant"):
        bootstrap_canonical("f", ("g", "i"), [(1, -1), (2, -2)], [(1, -1), (2, -2)], (1.0, 1.0))
