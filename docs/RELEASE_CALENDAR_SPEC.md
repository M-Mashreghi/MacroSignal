
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

## BEA Adapter (Task 2.8)

`macrosignal.calendar.bea` turns BEA schedule entries (an iCalendar feed via
`parse_bea_ics`, or extracted `(title, aware timestamp)` rows via
`parse_bea_schedule_rows`) into `ReleaseEvent`s with Eastern Time semantics:

- `GDP` (quarterly): `advance`, `second` and `third` estimates are separate
  events (`GDP-<year>Q<q>-<stage>`); annual / comprehensive updates are
  `benchmark_revision`. Title variants such as `GDP (Advance Estimate), 3rd
  Quarter 2026`, `Gross Domestic Product, Second Quarter 2026 (Third
  Estimate)` and `4th Quarter and Year 2026` are recognised.
- `PCE` (monthly): `Personal Income and Outlays, <Month> <Year>` is the initial
  release of that month (`PCE-<year>-<mm>`).
- Combined titles yield one event per family; unrecognised titles are skipped
  and listed.
- Advance < second < third must be scheduled in chronological order and each
  (family, period, stage) appears once, so estimate rounds are never collapsed.

No BEA feed URL is hard-coded; `fetch_bea_calendar(http, url)` requires a
caller-verified official URL. Actual release times follow the same opt-in
`confirm_past_events` rule as the BLS adapter.
