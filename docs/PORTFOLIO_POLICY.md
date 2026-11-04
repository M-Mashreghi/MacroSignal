
# Portfolio Policy

## Baselines

1. Equal weight
2. Static diversified allocation
3. Volatility-targeted static allocation
4. Signal long/flat
5. Risk parity
6. Constrained mean-variance research baseline

## Constraints

Validate:
- finite weights,
- sum constraint,
- leverage bound,
- per-asset bounds,
- turnover,
- optional shorting policy.

## Risk Estimates

Use only historical data available at rebalance time.

No future realized volatility or covariance.

## Practical v1

Prefer robust transparent portfolios over unstable unconstrained optimization.

## Tradable Universe (Task 5.1)

`macrosignal.portfolio.universe.UniverseResolver(config, metadata)` combines
the configured asset universe with per-asset `AssetMetadata`, rejecting role
mismatches, metadata for unconfigured assets, unsupported lifecycle policies,
and (for `provider_first_valid`) coverage that does not start at the first
tradable date. `tradable_on(d)` returns the assets tradable on `d` and an
explicit exclusion reason for every other configured asset (`no_metadata`,
`before_inception`, `after_last_tradable`, `outside_coverage`), so ETF proxies
are never used before their inception; `universe_series(days)` evaluates it per
execution date.

## Ex-Ante Risk Estimates (Task 5.4)

`macrosignal.portfolio.risk.estimate_covariance(returns, rebalance_session,
fit_time, RiskSettings(...))` uses only research returns of sessions strictly
before the rebalance session (unless `include_rebalance_session`), over the
last `lookback` sessions, on complete-case rows; assets with fewer than
`min_observations` returns are excluded with a reason, never filled. Methods:
`sample`, `ledoit_wolf` (shrinkage baseline, default) and `ewma` (half-life).
Estimates are annualized (`periods_per_year`, default 252) and record the
estimation window, number of observations, method, shrinkage and fit time.

## Target Weights & Baselines (Task 5.9)

`macrosignal.portfolio.allocation.TargetWeights` is the common output of every
method: weights per tradable asset, an explicit `cash_weight` (asset weights
plus cash sum to 1, all finite), the `CashReturnSpec` that cash earns, the
method and notes. Baselines: `equal_weight(universe, cash)` (1/N over the
assets tradable on the date; all cash if none) and `static_allocation(universe,
StaticAllocationSpec, cash)` (declared non-negative weights summing to at most 1;
weights of assets not yet tradable go to cash by default or are redistributed
pro rata with `unavailable_policy: renormalize`, with notes either way).
`RebalanceSchedule(frequency)` lists daily, weekly (first session of each ISO
week) or monthly (first session of each month) rebalance sessions.

## Long / Flat Portfolio (Task 5.10)

`macrosignal.portfolio.long_flat.long_flat_weights(scores, universe,
LongFlatSettings, cash)` holds assets whose score exceeds `min_score` and keeps
all others flat (never short). Longs are sized proportionally to score or
equally, scaled to `max_gross`, and capped at `max_weight`; capped excess is
held in cash, not redistributed. Scores for non-tradable assets are ignored
with a note, and all unallocated capital is cash earning the declared
`CashReturnSpec`.

## Volatility Targeting (Task 5.11)

`macrosignal.portfolio.vol_target.vol_target(base, estimate, VolTargetSettings)`
scales the risky part of a base allocation by `target_vol / sigma_base`, where
`sigma_base` is the ex-ante volatility from the covariance estimate fitted at
the rebalance (estimates from later sessions are refused). The applied scale is
capped by `max_scale` and gross exposure by `max_gross` (1.0 = no leverage);
uninvested capital is cash. If a held asset has no estimate (or volatility is
zero) the safe `fallback` keeps base weights unscaled (`unscaled`, default) or
moves everything to cash (`cash`). `VolTargetDiagnostics` records target, base
and final ex-ante volatility, raw / applied scale, caps, fallback and the
estimate's fit time and window.
