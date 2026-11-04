
# Signal Design

Signals are intentionally transparent.

## Component 1 — Regime Score

Consumes canonical aligned regime identities or aligned state probabilities.

Never consume raw HMM/GMM state numbers across refits.

## Component 2 — Surprise / Forecast-Error Score

Uses only valid pre-release expectation errors.

## Signal Decay

A release effect does not persist forever.

Each event family may define:
- immediate weight,
- half-life / decay,
- max persistence,
- replacement rule when a newer release arrives.

Example:

```text
signal_weight(age) = exp(-lambda * age)
```

The exact form is configurable and selected on training/validation only.

## Component 3 — Trend Guardrail

Optional market trend feature.

## Combined Score

```text
asset_score =
    w_regime * regime_component
  + w_surprise * decayed_surprise_component
  + w_trend * trend_component
```

## Ablations

Always compare:
- regime only,
- surprise/forecast-error only,
- trend only,
- regime + surprise,
- full combined model.

## Regime Score (Task 5.5)

`macrosignal.signals.regime_score.regime_scores(state, mapping, assets,
policy)` computes `score_a = w x sum_s P(s) x M[s, a]` from a live, aligned
regime observation (hard labels count as probability 1), a `RegimeAssetMap`
and the low-confidence weight `w` from Task 4.7. Maps are either `declared`
(a-priori preferences) or `learned` by `learn_regime_map(rows, cutoff, ...)`
as the mean forward return per (dominant regime, asset) using only rows whose
forward window ended by the training cutoff, with a minimum sample per cell
(fewer samples give preference 0 and a note). A learned map fitted after the
decision time is refused. Each score carries its per-regime decomposition, the
raw score and the confidence weight applied.
