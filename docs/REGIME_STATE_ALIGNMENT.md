
# Regime State Alignment

## Why It Is Required

Latent model state numbers have no intrinsic meaning.

Example:

```text
Walk-forward fit A:
state 0 = inflationary slowdown
state 1 = growth

Walk-forward fit B:
state 0 = growth
state 1 = inflationary slowdown
```

If a strategy assumes raw state id stability, the signal breaks.

## Canonical State Identity

Store canonical identities separately from model indices.

Example:

```text
growth_disinflation
growth_inflation
slowdown_inflation
slowdown_disinflation
```

For data-driven models, these names are interpretations; raw model state remains
available.

## Alignment Inputs

Candidate state descriptors:
- macro feature centroid,
- inflation factor,
- growth factor,
- labor factor,
- rates factor,
- transition persistence.

Do not align using future asset returns in a live strategy pipeline.

## Matching

After a refit:
1. compute state descriptor matrix,
2. compare with prior canonical descriptors,
3. solve one-to-one matching,
4. store mapping,
5. compute confidence / distance,
6. flag ambiguous matches.

A Hungarian / minimum-cost assignment is a suitable v1 method.

## New / Missing States

If state count changes:
- do not silently force a misleading map,
- create a model-version boundary,
- require explicit policy.

## Audit Artifact

Each refit stores:

```text
model_fit_id
raw_state_id
canonical_state_id
matching_distance
alignment_confidence
prior_fit_id
```

## Signals

Signals consume canonical state IDs or probability vectors after alignment.

## Regime State Data Model (Task 4.2)

`macrosignal.domain.regime.RegimeObservation` records `as_of`, `fit_id`,
`model_version`, `fit_cutoff`, `probability_type` (`hard_rule`,
`mixture_posterior`, `filtered`, `predicted`, `smoothed`), `kind`
(`hard_label` with raw / canonical state id, or `probability_vector` with raw
and optional canonical probabilities), `alignment_confidence` and a
`diagnostic` flag. Vectors must be non-negative and sum to one, with matching
raw / canonical state counts; hard labels may not carry vectors. `smoothed`
(future-informed) can only be constructed with `diagnostic=True`, live
observations need `fit_cutoff <= as_of`, and aligned latent states need an
alignment confidence. `require_live_states()` is the gate for signal and
backtest code: it rejects diagnostic, future-informed and unaligned states.

## Implementation (Task 4.6)

`macrosignal.regimes.alignment`: `bootstrap_canonical(fit, ...)` names the
first fit's states by the quadrant of their standardized growth / inflation
means (two states in one quadrant is an error). `align_states(fit_id,
means_original, canonical)` matches new state centroids to the canonical
descriptors with a deterministic Hungarian assignment on scale-normalized
Euclidean distance, storing per state `matching_distance` and
`alignment_confidence = 1 - d_assigned / d_second_best`; mappings below
`min_confidence` (default 0.3) or above `max_distance` are flagged
`ambiguous`, and a different state count gives status `state_count_changed`
with no mapping. `apply_alignment(states, result)` adds canonical ids /
probabilities (confidence = minimum mapping confidence) and refuses non-OK
results or states from another fit; `roll_forward` takes the next canonical
descriptors from the aligned fit. The audit fields (`model_fit_id`,
`raw_state_id`, `canonical_state_id`, `matching_distance`,
`alignment_confidence`, `prior_fit_id`) are on `AlignmentResult`.
