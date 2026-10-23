
# MacroSignal — Point-in-Time Macro Regime & Cross-Asset Strategy Engine

MacroSignal is a practical quant-macro research platform for studying whether
information **actually available to the market at the time** can identify useful
macro states and improve cross-asset research or allocation.

The project is designed around a hard constraint:

> A good backtest is impossible if chronology is wrong.

## What the Finished Project Does

```text
Official Macro Sources
        ↓
Raw Versioned Snapshots
        ↓
Availability Resolver
        ↓
Point-in-Time / Vintage Store
        ↓
Ragged-Edge Macro Panel
        ↓
Expectations / Forecasts
        ↓
Surprises / Forecast Errors
        ↓
Macro Regime Models
        ↓
Cross-Asset Event Studies
        ↓
Signals + Decay
        ↓
Portfolio Construction
        ↓
Walk-Forward Execution
        ↓
Robustness / Statistics
        ↓
Dashboard + Decision Audit
```

## Practical v1 Scope

- United States macro
- daily cross-asset research
- monthly / quarterly macro releases
- official release calendars
- official or archived macro vintages
- daily ETF / index proxies for the demo
- transparent regime models
- simple portfolio methods
- Streamlit dashboard
- no live trading

## Primary Data Sources

### Macro and release timing
- FRED / ALFRED
- BLS
- BEA
- Federal Reserve / FOMC calendar
- U.S. Treasury

### Market data
A provider interface is used so the demo source can later be replaced by an
institutional source.

## Two Expectation Modes

### Market Surprise Mode

```text
Initial Actual - Pre-release Consensus
```

Requires a valid historical consensus record available before release.

### Free Research Mode

```text
Initial Actual - Pre-release Model Forecast
```

This output is called **forecast error**, not market surprise.

## Important v3 Improvements

### Availability precision
ALFRED/FRED real-time metadata are often date-level, while official release
calendars may provide exact times.

MacroSignal therefore tracks whether availability is:
- exact timestamp,
- release date only,
- inferred end-of-day,
- provider timestamp,
- unknown.

### Ragged-edge macro state
GDP, CPI, payrolls, PCE, and rates are not equally fresh on a given day.

MacroSignal tracks:
- feature age,
- staleness,
- last availability,
- reference-period age.

### Stable regime identities
HMM/GMM state numbers can permute between walk-forward refits.

MacroSignal explicitly aligns latent states to stable canonical identities before
signals use them.

### Asset lifecycle
ETF proxies are only tradable after inception.

The backtest cannot use an instrument before its availability date.

### Return contract
Price return, total return, adjusted price, execution price, and cash return are
explicit instead of implicit.

### Signal decay
A macro surprise does not remain equally relevant forever.

Surprise signals have configurable decay / persistence policies.

## Demo Asset Universe

A configurable demo may include:
- SPY
- QQQ
- SHY
- TLT
- TIP
- GLD
- UUP
- USO

These are research defaults, not investment recommendations.

## Regime Models

- rule-based macro quadrants,
- Gaussian Mixture Model,
- Hidden Markov Model,
- PCA / dynamic-factor macro state.

## Portfolio Baselines

- equal weight,
- static diversified allocation,
- long/flat score,
- volatility targeting,
- risk parity,
- constrained mean-variance research baseline.

## Mandatory Backtest Gate

Before every decision:

```text
max(required_input.available_at) <= decision_timestamp
```

If false:

```text
BLOCK RUN
```

## Deliverables

The final repository should produce:
- PIT macro panel,
- release calendar,
- data-freshness matrix,
- consensus / forecast table,
- surprise / forecast-error table,
- macro factors,
- regime probabilities,
- state-alignment diagnostics,
- event studies,
- signal table,
- portfolio weights,
- walk-forward backtest,
- gross/net performance,
- selection-bias disclosure,
- research report,
- Streamlit dashboard,
- historical decision audit trail.

## Claude Code Workflow

Every task:

```text
Implement
→ Test
→ PIT / Leakage Check
→ Update Docs
→ git diff --check
→ Commit
→ Push
→ Verify
→ STOP
```

Start with Task 1.1 in `docs/PROJECT_PHASES_AND_TASKS.md`.

## Final Design Audit

The frozen design decisions, intentional limitations, and implementation release
criteria are documented in `docs/FINAL_AUDIT.md`.
