
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
