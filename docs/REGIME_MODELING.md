
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
