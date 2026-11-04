"""Regime persistence, transition and alignment diagnostics.

Computed from a chronological sequence of (aligned) regime observations and the
alignment results of successive refits:

* occupancy - share of decision times per dominant canonical state;
* durations - run lengths of the dominant state (mean / max per state);
* empirical transition matrix between consecutive dominant states;
* refit stability - number of refits, OK / ambiguous / state-count-changed
  counts, minimum and mean alignment confidence;
* per-state flags - ``rare`` (occupancy below ``min_occupancy``), ``unstable``
  (mean duration below ``min_mean_duration``) and ``weakly_aligned`` (minimum
  mapping confidence below ``min_alignment_confidence``).

Thresholds live in :class:`DiagnosticThresholds`.  :meth:`RegimeDiagnostics.
report_tables` returns plain rows and :meth:`to_canonical_json` a stable
serialization for the research report artifact.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from macrosignal.domain.manifest import canonical_json
from macrosignal.domain.regime import RegimeObservation
from macrosignal.regimes.alignment import AlignmentResult, AlignmentStatus


class DiagnosticThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_occupancy: float = Field(default=0.05, ge=0, le=1)
    min_mean_duration: float = Field(default=2.0, ge=0)
    min_alignment_confidence: float = Field(default=0.3, ge=0, le=1)


class StateDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: str
    occupancy: float
    n_spells: int
    mean_duration: float
    max_duration: int
    min_alignment_confidence: float | None
    rare: bool
    unstable: bool
    weakly_aligned: bool


class RefitStability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    n_refits: int
    n_ok: int
    n_ambiguous: int
    n_state_count_changed: int
    min_confidence: float | None
    mean_confidence: float | None


class RegimeDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    n_observations: int
    n_unassigned: int
    states: tuple[StateDiagnostics, ...]
    transition_matrix: dict[str, dict[str, float]]
    refit_stability: RefitStability
    thresholds: DiagnosticThresholds

    @property
    def flagged_states(self) -> list[str]:
        return [s.state for s in self.states if s.rare or s.unstable or s.weakly_aligned]

    def report_tables(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "states": [s.model_dump() for s in self.states],
            "transitions": [
                {"from": a, "to": b, "probability": p}
                for a, row in sorted(self.transition_matrix.items())
                for b, p in sorted(row.items())
            ],
            "refit_stability": [self.refit_stability.model_dump()],
        }

    def to_canonical_json(self) -> str:
        return canonical_json(self)


def regime_diagnostics(
    states: Sequence[RegimeObservation],
    alignments: Sequence[AlignmentResult] = (),
    thresholds: DiagnosticThresholds | None = None,
) -> RegimeDiagnostics:
    th = thresholds or DiagnosticThresholds()
    ordered = sorted(states, key=lambda s: s.as_of)
    labels = [s.dominant_state for s in ordered]
    assigned = [x for x in labels if x is not None]
    n = len(assigned)
    occupancy = {k: v / n for k, v in Counter(assigned).items()} if n else {}

    spells: dict[str, list[int]] = defaultdict(list)
    prev: str | None = None
    run = 0
    for label in labels:
        if label is not None and label == prev:
            run += 1
            continue
        if prev is not None:
            spells[prev].append(run)
        prev, run = label, 1 if label is not None else 0
    if prev is not None:
        spells[prev].append(run)

    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for a, b in zip(labels, labels[1:], strict=False):
        if a is not None and b is not None:
            counts[a][b] += 1
    transition = {
        a: {b: c / sum(row.values()) for b, c in row.items()} for a, row in counts.items()
    }

    conf_by_state: dict[str, list[float]] = defaultdict(list)
    for res in alignments:
        for m in res.mappings:
            conf_by_state[m.canonical_state_id].append(m.alignment_confidence)

    state_rows: list[StateDiagnostics] = []
    for state in sorted(set(occupancy) | set(conf_by_state)):
        durations = spells.get(state, [])
        mean_d = sum(durations) / len(durations) if durations else 0.0
        confs = conf_by_state.get(state)
        min_conf = min(confs) if confs else None
        occ = occupancy.get(state, 0.0)
        state_rows.append(
            StateDiagnostics(
                state=state,
                occupancy=occ,
                n_spells=len(durations),
                mean_duration=mean_d,
                max_duration=max(durations, default=0),
                min_alignment_confidence=min_conf,
                rare=occ < th.min_occupancy,
                unstable=mean_d < th.min_mean_duration,
                weakly_aligned=min_conf is not None and min_conf < th.min_alignment_confidence,
            )
        )

    all_conf = [m.alignment_confidence for r in alignments for m in r.mappings]
    stability = RefitStability(
        n_refits=len(alignments),
        n_ok=sum(r.status is AlignmentStatus.OK for r in alignments),
        n_ambiguous=sum(r.status is AlignmentStatus.AMBIGUOUS for r in alignments),
        n_state_count_changed=sum(
            r.status is AlignmentStatus.STATE_COUNT_CHANGED for r in alignments
        ),
        min_confidence=min(all_conf) if all_conf else None,
        mean_confidence=sum(all_conf) / len(all_conf) if all_conf else None,
    )
    return RegimeDiagnostics(
        n_observations=len(ordered),
        n_unassigned=len(labels) - n,
        states=tuple(state_rows),
        transition_matrix=transition,
        refit_stability=stability,
        thresholds=th,
    )
