
# Return & Execution Contract

## Asset Lifecycle

Each instrument stores:
- inception / first-tradable date,
- optional delisting/end date,
- provider coverage start,
- currency,
- exchange/timezone.

A backtest cannot use an ETF before it exists.

## Price Fields

Every provider documents:
- raw open/high/low/close,
- adjusted close,
- split adjustment,
- dividend adjustment,
- total-return availability.

Do not assume all "adjusted" fields mean the same thing across providers.

## Research Return

Every experiment specifies one return convention, for example:

```text
adjusted_close_to_adjusted_close
```

or a provider-specific total-return series.

## Execution Return

Execution policy specifies:
- signal timestamp,
- decision timestamp,
- execution timestamp,
- execution field.

Do not create an impossible same-bar fill.

## Conservative Daily Presets

Examples:

### next_session_close
Use when the project prioritizes clean daily chronology over immediate event
capture.

### next_session_open
Allowed only if provider open-price semantics are documented and the signal was
formed before that opening auction/session.

### same_day_close
Allowed when signal is formed before close and the experiment intentionally
starts PnL after the closing execution.

The run manifest records the preset.

## Cash / Flat Capital

Uninvested cash must earn:
- explicit zero return, or
- an explicit risk-free / cash proxy.

Do not silently assume one.

## Risk-Free Rate

Performance metrics must declare whether Sharpe uses:
- zero,
- Treasury bill proxy,
- another documented risk-free series.

## Corporate Actions

The return engine must avoid split/dividend artifacts.

## Trading Calendar

Use an explicit U.S. trading calendar:
- holidays,
- weekends,
- early closes if relevant.

Macro release calendars and market trading calendars are different objects.

## Implementation (Task 1.8)

Typed contracts live in `macrosignal.domain.execution` (all frozen, unknown
fields rejected):

- `ResearchReturnSpec(convention, price_field, adjustment_policy)` accepts only
  the inputs listed in `RETURN_CONVENTION_INPUTS`:
  `adjusted_close_to_adjusted_close` needs `adjusted_close` /
  `split_and_dividend_adjusted`; `total_return_index` needs
  `total_return_index` / `total_return`; `close_to_close_price_only` needs a
  split-adjusted close (unadjusted closes would create split artifacts).
- `ExecutionPriceSpec(field, adjustment_policy)` must be a tradable `open` or
  `close` that is `unadjusted` or `split_adjusted`; dividend-adjusted values
  were never traded and are rejected as fill prices.
- `EXECUTION_PRESETS` defines `next_session_close`, `next_session_open` and
  `same_day_close` (execution field, session offset, and the event the signal
  must precede); `get_execution_preset()` rejects unknown names.
- `CashReturnSpec` (`zero`, or `proxy` with a `proxy_series_id`) and
  `RiskFreeSpec` (`zero`, `treasury_bill_proxy`, `documented_series`) make cash
  and Sharpe risk-free assumptions explicit.
- `ReturnExecutionContract` requires the execution price field to match the
  preset, and requires an explicit `reconciliation` policy
  (`research_returns_raw_fills_for_timing_and_costs`) whenever dividend-inclusive
  research returns are combined with raw/split-adjusted fills.
- `DecisionTimeline` stores `information_time <= signal_time <= decision_time <
  execution_time <= mark_time` (no same-instant fill) and `check_inputs()`
  raises `AvailabilityViolation` when any input's `available_at` is after the
  information time.
