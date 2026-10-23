
# Practical MVP

## Scope

**Geography:** U.S.  
**Market frequency:** daily  
**Macro frequency:** mixed monthly/quarterly/daily  
**Research mode:** point-in-time  
**Dashboard:** Streamlit  
**Execution:** research only

## End-to-End MVP

```text
Official Source Data
→ Raw Snapshots
→ Availability Resolution
→ PIT Snapshot
→ Ragged-Edge Feature Panel
→ Consensus / Forecast
→ Surprise / Forecast Error
→ Regime Model + State Alignment
→ Event Study
→ Decayed Asset Signals
→ Portfolio
→ Walk-Forward Execution
→ Robustness
→ Dashboard / Audit Trail
```

## Free Mode

Requires no paid historical consensus.

Uses:
- official macro data,
- official release calendars,
- free daily demo market data,
- pre-release rolling forecasts.

The output is `forecast_error`.

## Consensus Mode

User imports properly timestamped historical consensus.

The output may be `market_surprise`.

## MVP Acceptance

The MVP is accepted only if:
- PIT/vintage tests pass,
- availability precision is audited,
- ragged-edge staleness is preserved,
- latent states are aligned across refits,
- instruments are not used before inception,
- execution contract is explicit,
- cash return is explicit,
- costs are included,
- at least three strategy baselines run,
- audit trail reproduces a historical decision,
- clean-clone fixture pipeline passes.
