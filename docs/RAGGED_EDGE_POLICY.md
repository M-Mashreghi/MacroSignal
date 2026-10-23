
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
