
# Release Calendar Specification

## Why It Matters

A macro series frequency does not define when the market learned the value.

The release calendar is a first-class dataset.

## Canonical Fields

- source,
- release id,
- release name,
- scheduled timestamp,
- actual timestamp when available,
- source timezone,
- UTC timestamp,
- reference period,
- release stage,
- snapshot id.

## Initial Priority

- CPI
- Employment Situation / payrolls
- unemployment rate
- PPI
- Employment Cost Index
- GDP releases
- Personal Income and Outlays / PCE
- selected additional indicators only after source timing is trustworthy

## Timezones

Never store naive release timestamps.

Preserve:
- original timezone,
- normalized UTC.

Use timezone databases, not fixed UTC offsets.

## Calendar Revisions

Calendars change.

Preserve calendar snapshots instead of overwriting previous versions.
