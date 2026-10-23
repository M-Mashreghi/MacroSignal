
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
