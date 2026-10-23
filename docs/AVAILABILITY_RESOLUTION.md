
# Availability Resolution

## Problem

Different sources provide different timing precision.

Examples:
- ALFRED real-time/vintage metadata are date-oriented.
- BLS and BEA schedules publish exact release times for many releases.
- FOMC statements have explicit release timestamps.
- Treasury daily curve inputs reflect late-day observations.

A date alone must not be treated as midnight knowledge.

## Canonical AvailabilityStamp

```text
available_at
precision
availability_source
calendar_mapping_id
conservative_adjustment
```

## Precision

### exact_timestamp
Official source provides date + time + timezone.

### provider_timestamp
Vendor/source provides an event timestamp, but semantics must be documented.

### release_date_only
The source establishes the date but not exact time.

### inferred_eod
The observation is conservatively treated as available after end-of-day.

### unknown
Insufficient evidence to safely place the observation in event time.

## Resolver Precedence

Illustrative precedence:

```text
official exact release timestamp
> documented provider timestamp
> official release date only
> conservative inferred end-of-day
> unknown
```

ALFRED vintage dates establish revision chronology but do not automatically
supply intraday release time.

A BLS/BEA/Fed release mapping may enrich an ALFRED observation with exact release
time only when:
- release family is known,
- reference period matches,
- release stage matches,
- mapping is versioned.

## Conservative Rule

When uncertain, shift availability later rather than earlier.

## Audit

Every resolved timestamp stores:
- raw source timing,
- resolution rule,
- final availability,
- precision,
- resolver version.
