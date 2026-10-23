
# Backtest Policy

## Splits

Use:
- expanding-window walk-forward,
- rolling-window walk-forward.

Never random train/test splits for strategy evaluation.

## Required Timeline

Every decision has:

```text
latest_input_time
signal_time
decision_time
execution_time
mark_time
```

## Availability Gate

Before every decision:

```text
max(required_input.available_at) <= decision_time
```

Violation blocks the run.

## Asset Lifecycle Gate

Before assigning a weight:

```text
first_tradable_date <= execution_date <= last_tradable_date
```

Do not backfill instruments before inception.

## Execution

Use a named execution preset from
`RETURN_AND_EXECUTION_CONTRACT.md`.

## Returns

The backtest declares:
- research return convention,
- execution field,
- corporate-action adjustment,
- cash return.

## Costs

Report:
- gross,
- base-cost net,
- stressed-cost net.

## Hyperparameters

Tune on training/validation only.

Final test period remains untouched by selection.

## Benchmarks

At minimum:
- equal weight,
- static diversified allocation,
- volatility-targeted baseline,
- no-regime ablation,
- no-surprise ablation.

## Metrics

Use `PERFORMANCE_STATISTICS.md`.

## Search Registry

Every tried configuration is recorded.

No "best Sharpe" without search-context disclosure.
