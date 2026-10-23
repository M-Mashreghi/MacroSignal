
# Performance Statistics

## Core Metrics

- CAGR / annualized return,
- annualized volatility,
- Sharpe,
- Sortino where useful,
- max drawdown,
- Calmar,
- turnover,
- average gross/net exposure,
- hit rate where meaningful.

## Sharpe

The risk-free assumption must be explicit.

Report:
- gross Sharpe,
- net Sharpe.

## Uncertainty

For strategy comparison, support dependence-aware methods where appropriate:
- block bootstrap,
- bootstrap confidence intervals,
- Newey-West / HAC for relevant regressions.

## Search Bias

When many strategies are tried:
- report search breadth,
- include a selection-bias discussion,
- optionally compute probabilistic/deflated Sharpe diagnostics when assumptions are documented.

Do not present one optimized Sharpe as if it came from a single pre-specified
strategy.

## Regime Metrics

Include:
- return by regime,
- volatility by regime,
- time spent in regime,
- transitions,
- sample size.
