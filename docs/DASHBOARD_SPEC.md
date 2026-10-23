
# Dashboard Specification

Recommended: Streamlit reading immutable run artifacts.

## 1. Run Overview
- protocol id
- run id
- snapshot ids
- commit
- execution contract
- integrity status

## 2. Macro Snapshot
- growth / inflation / labor / rates factors
- feature age
- stale flags
- availability precision
- last release

## 3. Release Monitor
- release family
- reference period
- release stage
- exact/inferred timestamp
- initial actual
- expectation type
- surprise or forecast error

## 4. Yield Curve
- nominal / real curves
- slope / spreads
- late-day availability warning
- feature transformation definitions

## 5. Regimes
- aligned canonical state
- filtered probabilities
- state uncertainty
- transition matrix
- raw-to-canonical mapping
- alignment confidence
- smoothed state shown only as ex-post diagnostic

## 6. Event Studies
- release selector
- event window
- surprise buckets
- regime
- sample size
- overlap/contamination flags
- confidence intervals

## 7. Portfolio & Backtest
- tradable universe
- signal decomposition
- target / realized weights
- cash
- costs
- turnover
- gross/net curve
- drawdown
- benchmarks

## 8. Decision Audit
For any rebalance:
- decision/execution timestamp
- available macro vintages
- availability precision
- feature age
- expectation record
- aligned regime state
- decayed signals
- target weights
- execution field
- cash policy
- costs.
