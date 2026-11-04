
# Cross-Asset Event Study

## Event Key

Each event must have a timezone-aware release timestamp and reference period.

## Supported Windows

With daily data:
- release-day / next-day conventions,
- 1 trading day,
- 5 trading days.

With valid intraday data:
- 5 min,
- 30 min,
- 1 hour.

Do not mix these without declaring granularity.

## Outputs

By:
- release type,
- surprise sign,
- surprise bucket,
- macro regime,

report:
- sample size,
- mean return,
- median return,
- hit rate,
- confidence interval.

## Event Contamination

Flag:
- overlapping macro releases,
- major scheduled policy events,
- very close events where attribution is unclear.

## Event-to-Market Alignment (Task 4.11)

`macrosignal.event_study.alignment.align_event(event, calendar, precision)`
uses the release's *actual* time (scheduled-only events are refused) converted
to America/New_York and classifies it as `pre_open` (reacts in the same
session), `market_hours` (same session; its open precedes the event, flagged by
`open_is_post_event = False`), `post_close` (next session), `non_session`
(weekend / holiday / closure: next session) or `date_level` (date-only or
inferred precision: next session after the date, baseline before the date).
The baseline is the close of the last session strictly before the information
could be known; early closes use their 13:00 close. Event-time precision and
release stage are carried through; `unknown` precision cannot be aligned.

## Daily Return Windows (Task 4.12)

`macrosignal.event_study.daily_windows.daily_event_windows(alignment, asset,
prices, calendar)` computes close-to-close returns (frequency `daily`, price
field and adjustment declared) for four separate conventions: `release_day`
(session before the event date -> event-date session; contains the reaction
only for pre-open / market-hours events), `next_session` (event-date session or
last before -> next session; post-close / non-session events only), `1d`
(baseline -> first reacting session) and `5d` (baseline -> fifth session
counting the reacting one). Prices must exist exactly at the declared session
closes (`missing_price` otherwise, never filled); windows outside the asset's
coverage are `outside_lifecycle`; market-hours events are flagged
`includes_pre_event_trading`, so no intraday reaction is ever claimed.

## Intraday Interface (Task 4.13, optional in v1)

`macrosignal.event_study.intraday` defines the contract a future intraday
provider must meet: `IntradayBarSeries` (one asset / provider, fixed bar
frequency of at most six hours, explicit `bar_end` / `bar_start` timestamp
convention, timezone-aware strictly increasing bars), the `IntradayProvider`
protocol, `IntradayWindowSpec` (minutes before / after) and
`intraday_event_return` (last bar ending at or before `event - before` to the
first bar ending at or after `event + after`). Daily data are rejected: a
daily frequency, bar spacing that reveals daily sampling, or daily
`MarketObservation` lists. v1 ships `UnconfiguredIntradayProvider`, which
refuses to produce data.
