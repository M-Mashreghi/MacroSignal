
# Architecture Rules

Canonical flow:

```text
Source Adapter
→ Raw Snapshot
→ Normalized Domain Model
→ Point-in-Time Store
→ Release / Expectation Alignment
→ Features / Surprise
→ Regime Model
→ Event Study / Signal
→ Portfolio
→ Backtest
→ Evaluation / Report
```

Do not bypass layers by directly reading latest external data from a model or
backtest component.

Every research artifact must be traceable to snapshot/config/run ids.
