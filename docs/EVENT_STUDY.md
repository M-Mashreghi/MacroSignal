
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
