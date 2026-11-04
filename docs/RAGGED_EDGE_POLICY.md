
# Ragged-Edge Macro Panel Policy

## Problem

Macro data arrive asynchronously.

On a given trading day:
- payrolls may be 10 days old,
- CPI 20 days old,
- GDP several weeks old,
- Treasury yields same-day late afternoon,
- PCE may update on another schedule.

A rectangular forward-filled table hides this information.

## AsOfFeature

Every feature should carry:

```text
feature_name
value
available_at
reference_period
age_since_available
age_since_reference
stale
availability_precision
source_snapshot_id
```

## Forward Fill

Forward-fill is allowed only as a representation of the **last known state**.

It must preserve:
- original availability timestamp,
- age,
- staleness.

## Staleness

Staleness threshold is feature-specific.

Examples:
- daily rates: short threshold,
- monthly CPI: longer threshold,
- quarterly GDP: much longer threshold.

Thresholds belong in config, not hidden code.

## Missingness

Prefer explicit:
- missing,
- stale,
- unavailable,

over synthetic backfilling.

## Modeling

Models may include:
- feature age,
- stale indicator,
- release-since-last-update indicator.

This lets the model distinguish a fresh release from an old carried value.

## Daily State Refresh

The daily macro state updates when:
- a macro release occurs,
- a market/rates feature becomes available,
- a scheduled model refit occurs.

Do not recompute old states using future revisions.

## As-Of Features (Task 3.3)

`macrosignal.features.as_of_features.build_family_features(store, catalog,
family, t)` computes every configured transformation of a family from the
series' as-of view at `t` and returns a `FeatureSet` of `AsOfFeature`s with
value, units, seasonal adjustment, reference period, release stage,
`available_at` and precision, `age_since_available = t - available_at`,
`age_since_reference_days` (New York date of `t` minus the reference-period
end), the series' `stale_after_days`, `stale = age_since_reference_days >
stale_after_days`, feature version and input snapshot ids. A feature whose
latest period cannot be transformed (no history yet, or a gap) is listed in
`missing`; it never falls back silently to an older period.
`macrosignal.features.inflation.build_inflation_features` applies this to the
`inflation` family (CPI / PCE release families).
