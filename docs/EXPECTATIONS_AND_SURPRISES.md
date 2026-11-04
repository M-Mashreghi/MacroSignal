
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

## Consensus CSV Adapter (Task 3.11)

`macrosignal.surprises.consensus_csv.import_consensus_csv(text, events,
default_units=...)` imports the documented schema
(`examples/consensus_template.csv`; optional `release_stage` and `units`
columns). `release_id` (the release family) plus `reference_period` (and the
stage when given) must match exactly one *released* calendar event; timestamps
must carry a UTC offset; only `consensus` rows are accepted. The
`ConsensusImportReport` classifies every non-accepted row as `invalid`,
`unmatched`, `ambiguous` (e.g. several GDP estimate rounds without a stage) or
`post_release` (available at/after the actual release). Accepted rows become
`ConsensusExpectation`s keyed to the event's release id and can be served
through `ConsensusImport.provider()`. Files are read from a user path (keep
licensed data outside the repository); the snapshot id is a hash of the file
bytes.

## Pre-Release Forecast Baselines (Task 3.12)

`macrosignal.surprises.forecast_baseline.forecast_release(store, series,
transformation, release, model, lead=1 day)` creates a forecast at
`actual_release_at - lead`, trained only on the series' as-of view at that
moment (no target realization, no later revisions; inputs pass the
no-lookahead guard). Models: `naive` (last value), `ar` (AR(p) with intercept,
OLS) and `ridge_ar` (L2 penalty on lag coefficients, intercept unpenalized).
Output is a `ModelForecast` (model id / version `baseline-1:<id>`, training
cutoff = creation time, availability, input snapshot ids) wrapped in a
`BaselineForecast` labelled `forecast_error`; too little history yields a
skipped forecast with a reason. `rolling_forecasts` runs the rolling origin
over a set of releases in chronological order.

## Surprise Engine (Task 3.13)

`macrosignal.surprises.engine.compute_surprise(store, series, transformation,
release, service, mode)` returns a `SurpriseRecord` with
`raw_surprise = actual - expected`, labelled `market_surprise` (consensus),
`forecast_error` (model forecast) or `proxy_surprise` (proxy) by mode, with the
expectation type and provider kept explicit. The actual is the value of the
release's own stage (initial print, or the GDP advance/second/third estimate
the event published), transformed from the as-of view at the moment that
vintage became available, never a later revision. The expectation comes from
`ExpectationService` at the actual release time. Without a valid expectation
the status is `missing_expectation` (no surprise value); without the actual,
`missing_actual`. Units of actual and expectation must agree.

## PIT Standardization & Composites (Task 3.14)

`macrosignal.surprises.standardize.standardize_surprises(records, policy)`
standardizes one feature / one mode at a time with
`z_k = (raw_k - center) / scale(prior computed surprises)` where only releases
strictly before `k` enter (expanding, or the last `window`). Policy:
`min_history` (fewer priors -> `insufficient_history`, no z), `scale_method`
`std` (sample) or `mad` (1.4826 x MAD), `demean` (default off, so
z = raw / prior scale as specified above), and the outlier rule `winsorize_z`
(clip |z|, flag `clipped`; raw surprises never change). Zero scale or a missing
raw surprise gives no z.

`CompositeSpec(name, members=((feature, weight), ...), mode, max_age_days,
min_members)` declares fixed positive weights; `composite_as_of(spec,
standardized, t)` takes each member's latest z released by `t` and no older
than `max_age_days`, returns the weighted average when at least `min_members`
contribute, and lists contributions (release id, z, weight) and missing members.
All inputs must share the spec's mode, so market surprises and forecast errors
are never mixed.
