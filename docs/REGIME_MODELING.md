
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

## Model B Implementation (Task 4.3)

`macrosignal.regimes.training.training_matrix(frame, features, cutoff)` takes
complete-case rows of an `AsOfFeatureFrame` with decision time at or before the
cutoff (incomplete rows excluded and counted); `FrozenScaler` stores training
means / population standard deviations. `macrosignal.regimes.gmm.fit_gmm(frame,
GmmConfig(features, n_components, seed, n_init, ...), cutoff, fit_id)` fits a
full-covariance Gaussian mixture on the standardized training rows with a
fixed seed and stores weights, centroids (standardized and original units),
covariances, training occupancy, BIC, log-likelihood, convergence, training
window, cutoff and config (`params_hash` for audit). Rows after the cutoff
cannot change the fit. `GmmFit.posterior_state(t, row)` returns raw component
probabilities as an unaligned `mixture_posterior` `RegimeObservation`;
`fit_gmm_candidates` fits each configured state count.

## Model C Implementation (Task 4.4)

`macrosignal.regimes.hmm.fit_hmm(frame, HmmConfig(features, n_states, seed,
...), cutoff, fit_id)` fits a full-covariance Gaussian HMM by Baum-Welch with a
scaled forward-backward pass in numpy (no optional dependency) on standardized
training-window rows, initialized deterministically from a seeded Gaussian
mixture with raw states ordered by the first feature's mean. `HmmFit` stores
the transition matrix, initial distribution, state means (standardized and
original), covariances, training occupancy, log-likelihood, BIC, cutoff, seed,
iterations and convergence (`params_hash`). `filtered_states(frame)` emits
contemporaneous `filtered` probabilities for decision times at or after the
cutoff, each computed from rows up to that time only;
`smoothed_diagnostics(frame)` emits future-informed `smoothed` probabilities
that are always `diagnostic=True`.

## Filtered-vs-Smoothed Guard (Task 4.5)

`macrosignal.regimes.guard`: signal and backtest entry points take a
`LiveRegimeSeries`, constructible only from contemporaneous, aligned,
non-diagnostic states with strictly increasing decision times and
`fit_cutoff <= as_of`; the `@live_regime_input` decorator rejects anything
else (lists of raw states, `ExPostDiagnostics`). Smoothed probabilities can
only be held in `ExPostDiagnostics`, which has no conversion to the live type.
`verify_filtered_against_fit(fit, frame, states)` recomputes the
contemporaneous filter and rejects states whose probabilities differ (smoothed
numbers relabelled as `filtered`). `tests/regression/test_smoothed_leakage_guard.py`
attempts each leakage path and requires it to fail.

## Regime Confidence (Task 4.7)

`macrosignal.regimes.confidence.assess(state, policy)` reports, per regime
observation, `max_probability`, `normalized_entropy` (entropy / log K),
`alignment_confidence` (1.0 for rule labels, 0 when unaligned) and
`effective_confidence = sharpness x alignment_confidence` with
`sharpness = (max_probability - 1/K) / (1 - 1/K)`. `LowConfidencePolicy`
(`min_max_probability`, `max_normalized_entropy`, `min_alignment_confidence`,
`action`) marks low-confidence states with reasons; their `signal_weight` is 0
(no regime tilt). Otherwise `neutral` gives weight 1 and `scale` gives
`effective_confidence`. No action carries an old regime forward or rounds
probabilities up. `confidence_rows()` exposes all fields for research outputs
and the dashboard.

## Model D Implementation (Task 4.8)

`macrosignal.regimes.macro_pca.fit_macro_pca(frame, features, cutoff,
n_components=..., fit_id=...)` fits principal components of standardized
macro / rates / curve-shape features on complete-case training rows at or
before the cutoff (other cell kinds are refused, so the state never depends on
asset returns), with deterministic signs (largest absolute loading positive),
and freezes scaler, loadings, explained variance and cutoff (`params_hash`).
`factor_states(frame)` applies the frozen transform to every complete row and
flags rows at or before the cutoff as `in_sample`.
