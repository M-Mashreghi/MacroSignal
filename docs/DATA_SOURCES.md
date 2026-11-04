
# Data Sources

## FRED / ALFRED

Use for macro series and revision/vintage reconstruction.

Important:
- real-time periods are date-oriented,
- vintage dates track when values were first released or revised,
- initial-release output is available for series observations.

Do not infer exact intraday release time from a vintage date alone.

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
