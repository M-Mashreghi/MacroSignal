
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
