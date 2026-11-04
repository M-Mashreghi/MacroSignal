
# Evaluation Protocol

## 1. Data Integrity
- vintage correctness,
- exact/inferred availability correctness,
- release-stage correctness,
- asset lifecycle correctness,
- snapshot reproducibility.

## 2. Ragged-Edge Integrity
- staleness preserved,
- no hidden future fill,
- release updates propagate only after availability.

## 3. Feature Integrity
- transformation definition explicit,
- standardization training-only,
- PCA training-only.

## 4. Regime Quality
- persistence,
- stability,
- minimum occupancy,
- canonical state alignment,
- alignment confidence,
- transition behavior,
- interpretability.

## 5. Event Research
- sample size,
- overlap / event contamination,
- effect size,
- uncertainty,
- release-stage consistency.

## 6. Strategy
- OOS performance,
- drawdown,
- turnover,
- costs,
- cash assumption,
- concentration,
- asset availability,
- benchmark comparison.

## 7. Robustness
- alternative execution delays,
- alternative regime models,
- alternative signal decay,
- alternative costs,
- subperiods,
- crisis/non-crisis,
- asset ablations,
- signal ablations.

## 8. Selection Bias
- number of tried variants,
- selected metric,
- test set untouched,
- optional deflated/probabilistic Sharpe diagnostics.

Negative and null findings remain in the report.

## Protocol Registry (Task 1.12)

Hypotheses are pre-registered as `macrosignal.protocol.ResearchProtocol`:
`protocol_id`, integer `version`, `status` (`exploratory` / `confirmatory`),
`hypothesis`, `null_result_statement`, `target`, `horizons` (e.g. `1d`, `5d`),
`universe`, `metrics` with a `primary_metric`, and a chronological
`sample_policy` (expanding or rolling walk-forward development window plus an
optional held-out test window that must start after development ends; a
confirmatory protocol requires the test window).

`ProtocolRegistry(root)` stores each version as canonical JSON
(`<root>/<protocol_id>/v<version>.json`) with its content hash. Registered
versions are frozen: re-registering identical content is a no-op, different
content raises `ProtocolMutationError`, versions must be consecutive from 1,
and a stored file whose content no longer matches its hash raises
`ProtocolIntegrityError`. `require_for_run(run)` resolves a `ResearchRun`'s
`protocol_id` / `protocol_version` to its frozen protocol and refuses runs that
reference an unregistered version (or a label such as `latest`).
