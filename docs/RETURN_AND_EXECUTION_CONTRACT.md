
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

## Trading Calendar & Demo Market Data (Task 2.14)

`macrosignal.calendar.trading.UsTradingCalendar` is a rule-based NYSE calendar
for 2000-2099 (dates outside raise `CalendarRangeError`): weekends; New Year's
(Saturday not observed), MLK, Washington's Birthday, Good Friday, Memorial,
Juneteenth (from 2022), Independence Day, Labor, Thanksgiving and Christmas
with Saturday->Friday / Sunday->Monday observance; documented special closures
(2001-09-11..14, 2004-06-11, 2007-01-02, 2012-10-29/30, 2018-12-05, 2025-01-09,
extensible); 13:00 ET early closes on July 3 before a weekday Independence
Day, the day after Thanksgiving and December 24. It provides sessions,
next/previous session and session open (09:30) / close timestamps.

`macrosignal.data.market` defines the provider-neutral `MarketDataProvider`
interface and one demo provider, `YahooDemoProvider` (optional `yfinance`,
extra `market-demo`, demo only). Field semantics are explicit: with
`auto_adjust=False`, `Open/High/Low/Close/Volume` are `split_adjusted` and
`Adj Close` is `split_and_dividend_adjusted`. `normalize_daily_bars` stamps open
fields at the session open and other fields at the session close (13:00 on
early-close days), rejects rows on non-sessions, duplicate or post-retrieval
dates, reports `missing_sessions` and `missing_values` without filling them,
and derives conservative `AssetMetadata` coverage/inception from the provider's
first valid row. `cache_raw_batch` stores the raw payload and provider metadata
as an immutable `raw_snapshot` artifact.

## Research Return Engine (Task 5.2)

`macrosignal.portfolio.returns.compute_returns(asset, prices, spec, calendar,
start, end)` computes session-to-session research returns, separately from
execution simulation. Prices must use exactly the spec's field and adjustment
policy, sit at the trading calendar's session closes (13:00 on early closes)
and belong to the asset, whose declared return convention must match the spec.
Only sessions inside the asset's lifecycle and coverage count; a session
without a price makes the returns into and out of it missing (listed in
`missing_sessions`, never bridged). One-session moves above `max_abs_return`
(default 35%) are flagged as suspected unadjusted corporate actions and can be
made fatal with `reject_suspicious=True`.

## Cash / Risk-Free Engine (Task 5.3)

`macrosignal.portfolio.cash.cash_returns(spec, calendar, start, end, rates)`
implements the declared `CashReturnSpec`: `zero` is exactly 0 per session;
`proxy` accrues a short-rate series (annualized percent) as simple ACT/360
interest over each `previous close -> close` period, using the latest rate
whose `available_at` is at or before the period's start. Without such a rate
the period is missing, never zero. Every period records rate, observation date,
availability and day count. `risk_free_returns` applies the same engine to the
`RiskFreeSpec` used by Sharpe-type metrics; `rates_from_macro` and
`rates_from_curve` adapt daily macro observations or Treasury curve tenors.
