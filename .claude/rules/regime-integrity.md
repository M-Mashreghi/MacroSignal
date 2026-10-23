
# Regime Integrity Rules

Contemporaneous strategy states use only training/history data.

## HMM
- filtered probabilities: allowed,
- smoothed probabilities: ex-post only.

## State identity
HMM/GMM numeric state IDs are arbitrary and may permute after refitting.

Every refit must:
1. compute state descriptors/centroids,
2. align new states to stable canonical identities,
3. store the mapping,
4. expose mapping confidence,
5. flag ambiguous alignment.

Signals must use canonical state identities, never raw state numbers.

## Fitting
Scaler/PCA/GMM/HMM fitting uses training history only.

Future returns must not be used to rename states for contemporaneous strategy
formation.
