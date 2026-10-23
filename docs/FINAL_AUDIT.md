# MacroSignal — Final Architecture Audit

Status: **FINAL DESIGN PACKAGE**

## What Was Checked

- point-in-time vintage policy,
- availability precision,
- release calendar mapping,
- ragged-edge feature freshness,
- surprise vs forecast-error terminology,
- GDP/release-stage handling,
- FOMC event separation,
- HMM filtered-vs-smoothed leakage,
- GMM/HMM state label alignment,
- asset inception / lifecycle,
- return and execution semantics,
- cash / risk-free policy,
- transaction costs and turnover,
- event overlap / contamination,
- model-selection leakage,
- search / selection bias,
- task dependencies,
- Git workflow,
- config consistency,
- internal documentation links,
- package bootstrap and CI validation.

## Final Design Decisions

### Daily-first MVP
The first defensible release is a daily U.S. macro research platform. Intraday
support is an interface/extension until a timestamped institutional-quality
intraday dataset is connected.

### Free mode vs consensus mode
Free mode produces model **forecast errors**. Only valid pre-release consensus
records produce **market surprises**.

### Availability is conservative
When exact timing cannot be established, the system uses a later conservative
availability or excludes the observation rather than moving information earlier.

### Latent states are aligned
Raw GMM/HMM state numbers are never assumed stable across walk-forward refits.

### Tradability is historical
Assets cannot be traded before actual provider coverage / first-tradable date.

### Performance is net-aware
Research reports include transaction costs, turnover, cash policy, and explicit
return conventions.

## Known Intentional Limitations

These are not bugs and should not be silently expanded during v1:

- U.S.-focused rather than global macro,
- daily demo market data rather than mandatory intraday data,
- no bundled proprietary consensus history,
- no live brokerage execution,
- no derivatives / options portfolio,
- no high-frequency infrastructure,
- no neural forecasting required,
- demo market-data adapters are not claimed to be institutional-grade.

## Release Gate

The implementation is portfolio-ready only when:

1. all 104 task definitions are resolved,
2. PIT / chronology tests pass,
3. clean-clone fixture reproduction passes,
4. backtest regression fixture passes,
5. dashboard audit trail reconstructs a historical decision,
6. gross/net/benchmark/robustness outputs are produced,
7. no secrets or restricted data are committed,
8. final GitHub history is task-scoped and pushed.
