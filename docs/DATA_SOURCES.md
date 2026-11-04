
# Data Sources

## FRED / ALFRED

Use for macro series and revision/vintage reconstruction.

Important:
- real-time periods are date-oriented,
- vintage dates track when values were first released or revised,
- initial-release output is available for series observations.

Do not infer exact intraday release time from a vintage date alone.

Transport (Task 2.2): `macrosignal.data.fred.FredClient` wraps
`fred/series`, `fred/series/release`, `fred/series/observations` (with
`realtime_start` / `realtime_end` / `vintage_dates` / `output_type`),
`fred/series/vintagedates` and `fred/release/dates`. It requires
`FRED_API_KEY` (raising `MissingCredentialError` otherwise), follows
`limit`/`offset` pagination until `count` is reached, rejects FRED error
envelopes and malformed responses, and returns raw records plus the raw
snapshot ids they came from; normalization is a separate step.
`configured_series_ids(registry)` lists the FRED series of the macro registry.
Tests use synthetic response fixtures in `tests/fixtures/fred/` via the
offline `tests/fakes.py::FakeFred` transport.

## BLS

Use for:
- CPI,
- Employment Situation,
- PPI,
- ECI and selected labor/inflation releases,
- official release calendar.

BLS schedules commonly include exact Eastern Time release times.

## BEA

Use for:
- GDP,
- Personal Income and Outlays / PCE,
- national accounts,
- official release schedule and estimate stage.

Keep:
- advance / second / third estimate stage,
- reference period,
- release time.

## Federal Reserve

Use for:
- FOMC meeting/statement calendar,
- explicit policy-statement timestamps,
- selected official statistical releases where appropriate.

FOMC statements should be treated as separate event types from monthly macro
releases.

Do not infer a monetary-policy surprise from the announced rate change unless a
valid pre-meeting expectation measure exists.

## U.S. Treasury

Use for:
- daily nominal par yield curve,
- daily real yield curve.

Treasury indicates that nominal par-curve input quotations are obtained at
approximately 3:30 PM ET.

Therefore:
- do not use that day's curve in a morning decision,
- resolve its availability conservatively as late-day/end-of-day.

## Market Data

Use a provider-neutral adapter.

### Demo provider
Suitable for reproducible daily research demonstrations only.

Requirements:
- record provider,
- retrieval timestamp,
- adjustment policy,
- coverage/inception,
- raw snapshot/hash.

### Institutional provider
Can replace the demo adapter without changing research layers.

## Expectations / Consensus

Support:
- timestamped user CSV,
- institutionally licensed adapter,
- model-based pre-release forecast.

Never scrape or redistribute proprietary consensus history.

## Transport & Raw Snapshots (Task 2.1)

All source adapters fetch through `macrosignal.data.http.HttpClient`
(provider-neutral, synchronous `httpx`):

- explicit timeout; transport errors and HTTP 408/425/429/5xx are retried with
  capped exponential backoff (a bounded `Retry-After` is honoured) up to
  `max_attempts`, then `HttpRetryExhaustedError`;
- other 4xx (authentication, bad request, not found) raise
  `HttpNonRetryableError` immediately; malformed JSON raises
  `ResponseSchemaError` and is never retried;
- query parameters must be passed via `params=`; credential parameters
  (`api_key`, `registrationkey`, `UserID`, ...) are redacted to `***` in all
  stored metadata;
- each response becomes a `RawSnapshot` before normalization: sha256 of the raw
  payload plus a stable hash of the redacted request (source, method, URL,
  params). `snapshot_id = raw_<source>_<hash>` is independent of retrieval time
  and API key, so identical re-fetches are idempotent;
- `persist_snapshot` stores `payload.bin` and `request.json` as an immutable
  `raw_snapshot` artifact under `data/raw/<source>/` (git-ignored).

## FRED Series Metadata (Task 2.3)

`macrosignal.data.fred_metadata.fetch_series_metadata` combines `fred/series`
and `fred/series/release` into a frozen `SeriesMetadata`: title, units,
canonical `frequency` and `seasonal_adjustment` (unsupported FRED values such
as biweekly raise `MetadataNormalizationError` rather than being guessed),
observation range, `last_updated` (FRED's hour offset parsed as tz-aware),
release id/name, and the `metadata_snapshot_ids` of the raw responses.
`compare_definitions` reports units / frequency / seasonal-adjustment changes as
blocking and title / release changes as non-blocking; `assert_compatible`
raises `DefinitionChangeError` so incompatible histories are never merged
silently.

## ALFRED Vintage Dates (Task 2.4)

`macrosignal.data.alfred.fetch_vintage_dates` retrieves every vintage date of a
series into a `VintageDateSet` (strictly increasing, none after the retrieval
date, raw snapshot ids kept); `fetch_pit_vintage_dates` does this for every
`pit_required` FRED series of the macro registry, and `persist_vintage_dates`
stores each set as an immutable `normalized` artifact
(`data/processed/normalized/vintages_<series>_<hash>/`). `vintage_history`
groups ALFRED observation records into per-reference-date revision chains
ordered by `realtime_start`, keeps ALFRED's `.` as an explicit missing value,
and rejects overlapping real-time periods or periods that do not start on a
known vintage. Vintage dates remain date-level availability evidence.
