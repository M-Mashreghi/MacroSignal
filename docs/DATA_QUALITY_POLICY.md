
# Data Quality Policy

## Ingestion Checks

For every source:
- duplicate key detection,
- monotonic / valid timestamps,
- unit consistency,
- frequency consistency,
- missing critical metadata,
- impossible release/reference relationships,
- parser schema drift.

## Vintage Checks

- duplicate vintages,
- non-monotonic revision chronology,
- initial-release missing,
- revision before initial release,
- conflicting source snapshots.

## Market Checks

- missing sessions,
- impossible nonpositive prices where not allowed,
- duplicate bars,
- adjustment discontinuities,
- coverage before instrument inception.

## Research Behavior

Blocking errors stop snapshot creation.

Warnings must be recorded in a data-quality artifact.

Do not auto-fix source anomalies invisibly.
