
# MacroSignal Architecture

```mermaid
flowchart LR
    F[FRED / ALFRED] --> RAW[Raw Snapshots]
    B[BLS] --> RAW
    E[BEA] --> RAW
    T[Treasury] --> RAW
    M[Market Provider] --> RAW
    C[Consensus / Forecast] --> RAW

    RAW --> N[Normalization]
    N --> PIT[Point-in-Time Store]
    PIT --> CAL[Release Alignment]
    CAL --> FEAT[Macro Features]
    CAL --> SURP[Surprises / Forecast Errors]

    FEAT --> REG[Regime Models]
    SURP --> REG
    SURP --> EVT[Event Studies]

    REG --> SIG[Signals]
    EVT --> SIG
    SIG --> PORT[Portfolio]
    PORT --> BT[Walk-Forward Backtest]
    BT --> EVAL[Evaluation]
    EVAL --> REP[Reports / Dashboard]
```

## Boundaries

### Data Layer
Only source adapters know external API schemas.

### PIT Layer
Owns as-of reconstruction and availability checks.

### Feature Layer
Owns transformations and training-only preprocessing.

### Regime Layer
Owns macro-state models and contemporaneous probabilities.

### Research Layer
Owns event studies and signal construction.

### Portfolio Layer
Owns weights, constraints, and risk scaling.

### Backtest Layer
Owns chronology, execution, turnover, costs, and benchmarks.

### Reporting Layer
Reads immutable result artifacts; it does not recompute research silently.

## Storage

Recommended v1:
- raw source payloads: files / compressed JSON/CSV where permitted,
- normalized tables: Parquet,
- metadata/manifests: JSON,
- local research registry: SQLite or Parquet manifest tables.

Do not require a distributed database for v1.
