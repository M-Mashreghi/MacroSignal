
# Expectations and Surprises

## Market Surprise Mode

Requires a pre-release consensus record.

```text
raw_market_surprise = actual_initial_release - consensus_before_release
```

Standardize with history available before the current release:

```text
z_surprise = raw_market_surprise / prior_surprise_scale
```

## Free Research Mode

If no consensus dataset is available:

```text
forecast_error = actual_initial_release - model_forecast
```

The forecast model:
- trains only on prior releases,
- records training cutoff,
- records forecast creation timestamp,
- never sees the target realization.

## Naming Rule

Do not label forecast error as "market surprise".

## Missing Expectation

If expectation is unavailable:
- market surprise = missing,
- release may still contribute level/momentum features,
- do not impute consensus from realized data.

## Composite Factors

Candidate:
- inflation surprise factor,
- labor surprise factor,
- growth surprise factor.

Aggregation weights must be transparent and point-in-time.

## Provider Interface (Task 3.10)

`macrosignal.surprises.expectations` defines `ExpectationProvider` (a `name`,
one declared `expectation_type`, and `expectations_for(release)`), a
`StaticExpectationProvider` that rejects records of another type, and
`ExpectationService.get(release, mode, as_of)`. Only providers of the type the
mode requires are consulted (`market_surprise` -> consensus, `forecast_error`
-> model forecast, `proxy_surprise` -> proxy). A candidate must be available by
`as_of` and pass `check_pre_release` against the actual release; the most
recently available valid candidate is chosen, simultaneous candidates with
different values raise `AmbiguousExpectationError`, and no valid candidate
yields status `missing` (never imputed). Rejected candidates are returned with
reasons. `expectation_rows()` always carries `mode` and `expectation_type`
columns into downstream tables.
