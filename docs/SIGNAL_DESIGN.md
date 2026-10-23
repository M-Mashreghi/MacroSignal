
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
