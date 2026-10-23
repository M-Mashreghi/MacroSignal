
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
