
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
