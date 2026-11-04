
# Regime Modeling

## Model A — Transparent Macro Quadrants

Conceptual axes:
- growth momentum,
- inflation momentum.

Example interpretation:
- growth up / inflation down: Goldilocks
- growth up / inflation up: Reflation
- growth down / inflation up: Stagflation
- growth down / inflation down: Slowdown / Disinflation

Thresholds must be defined from prior information only.

## Model B — Gaussian Mixture

Use point-in-time standardized macro features.

Fit only on training history.

## Model C — Hidden Markov Model

Outputs:
- state transition matrix,
- filtered probabilities,
- smoothed probabilities.

Trading / backtest:
- filtered only.

Ex-post interpretation:
- smoothed allowed when clearly labeled.

## Model D — PCA / Dynamic-Factor State

Build low-dimensional macro factors using training-only transforms.

## Model Comparison

Evaluate:
- persistence,
- transition stability,
- interpretability,
- state frequency,
- cross-asset separation,
- out-of-sample usefulness.

## Model A Implementation (Task 4.1)

`macrosignal.regimes.quadrants.classify_frame(frame, rule)` reads a growth and
an inflation feature from an `AsOfFeatureFrame` at each decision time and
assigns `growth_disinflation` (growth above / inflation below threshold),
`growth_inflation`, `slowdown_inflation` or `slowdown_disinflation`.
`QuadrantRule` declares the two features and `threshold_method`: `fixed`
(declared thresholds) or `expanding_median` / `expanding_mean` computed only
from values at earlier decision times, with `min_history`. Missing inputs,
stale inputs (unless `allow_stale`) and insufficient history give no label
with an explicit status. Each `QuadrantState` reports the label, input values,
their availability and the thresholds used.
