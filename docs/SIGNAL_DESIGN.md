
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

## Surprise Score with Decay (Task 5.6)

`macrosignal.signals.surprise_score.surprise_scores(standardized,
sensitivities, decay, t, assets, mode)` computes
`score_a = sum_f beta[f, a] x z_f x 0.5^(age_f / half_life)` from each
factor's latest standardized surprise released by `t` (a newer release
replaces the older one), with zero weight beyond `max_age_days`.
`DecayPolicy.from_config` reads `surprise_component.decay` from
`configs/signals/signals_v1.yaml` (exponential, half-life 10 days, max age 45).
All inputs must share one surprise mode, which labels the score
(`market_surprise` / `forecast_error`); factors without a usable z are listed
as missing (never imputed); each score carries per-factor contributions with
release id, age, z, decay and beta.

## Trend Guardrail (Task 5.7)

`macrosignal.signals.trend.trend_signals(returns, decision_session,
TrendSettings)` compounds each asset's research returns of sessions strictly
before the decision session within the last `lookback_days` calendar days
(`trend_component.lookback_days`, 60 in `signals_v1.yaml`), i.e. information up
to the previous close, and reports direction +1 / -1 / 0. Fewer than
`min_observations` returns gives status `missing` (no inferred direction); a
disabled component reports `disabled` for every asset so the trend can be
ablated. Each signal records its window bounds and the number of returns used.
