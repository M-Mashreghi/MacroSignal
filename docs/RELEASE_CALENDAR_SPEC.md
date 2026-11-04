
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

## BLS Adapter (Task 2.7)

`macrosignal.calendar.bls` parses the BLS news-release schedule iCalendar feed
(`https://www.bls.gov/schedule/news_release/bls.ics`) with a small RFC 5545
reader (`macrosignal.calendar.ics`). Times are Eastern Time: `TZID` values are
mapped through an explicit alias table (`US-Eastern` -> `America/New_York`),
`Z` means UTC, floating times use the documented Eastern default, and
date-only or unknown-`TZID` entries are rejected. Supported families: `CPI`,
`EMPLOYMENT_SITUATION`, `PPI` (monthly reference periods) and `ECI`
(quarterly); other titles are skipped and listed, never guessed. Each event's
`calendar_snapshot_id` is the raw snapshot id of the fetched feed (or a content
hash), and `diff_calendars` reports added / removed / rescheduled events
between snapshots, so schedule changes are preserved rather than overwritten.

A schedule is not proof of publication: `actual_release_at` stays empty unless
the caller opts in to `confirm_past_events`, which records an event still on a
calendar retrieved at least `confirmation_lag` (default one day) after its
scheduled time as released at that time.
