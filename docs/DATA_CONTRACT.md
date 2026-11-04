
# Data Contract

## AvailabilityStamp

```text
available_at
precision
availability_source
raw_available_date
calendar_mapping_id
resolver_version
conservative_adjustment
```

Precision:
- exact_timestamp
- provider_timestamp
- release_date_only
- inferred_eod
- unknown

Implemented as `macrosignal.domain.AvailabilityStamp` (Tasks 1.4/1.5, frozen,
unknown fields rejected). `available_at` (timezone-aware) and `precision` are
required; the audit fields are optional but validated when present:

- `availability_source` is one of `official_release_schedule`,
  `provider_timestamp`, `alfred_vintage_date`, `official_release_date`,
  `conservative_inference`, `unknown`, and must support the declared precision
  (e.g. `provider_timestamp` precision only from a provider timestamp, `unknown`
  source only with `unknown` precision).
- A date-level source (`alfred_vintage_date`, `official_release_date`) may claim
  `exact_timestamp` only with a versioned `calendar_mapping_id`, and a
  `calendar_mapping_id` requires `resolver_version`.
- `available_at` may not fall before `raw_available_date`, and a date-level
  precision (`release_date_only`, `inferred_eod`) may not be placed at midnight
  at the start of its raw date.
- `conservative_adjustment` is a non-negative `timedelta` (availability only
  moves later); `raw_available_at` recovers the pre-adjustment instant.

## MacroObservation

```text
source
series_id
release_family
release_id
release_stage
reference_start
reference_end
value
units
frequency
seasonal_adjustment
release_timestamp
availability: AvailabilityStamp
vintage_date
realtime_start
realtime_end
retrieved_at
source_snapshot_id
adapter_version
```

Implemented as `macrosignal.domain.MacroObservation` (frozen, unknown fields
rejected). Validation rejects naive datetimes, reference periods that are not a
single period of the declared `frequency`, availability or release on/before the
reference period end (same-day is allowed only for daily series), availability
earlier than `release_timestamp`, `retrieved_at` before availability,
`realtime_end < realtime_start`, availability before `vintage_date` /
`realtime_start`, and non-finite values. Chronology checks are date-level in each
timestamp's own timezone.

## ReleaseEvent

```text
release_id
release_family
release_name
source
scheduled_at
actual_release_at
source_timezone
reference_period
release_stage
calendar_snapshot_id
```

Implemented as `macrosignal.domain.ReleaseEvent` (Task 1.5, frozen, unknown
fields rejected). The reference period is stored as `reference_start` /
`reference_end` (optional as a pair, e.g. for FOMC statements); `release_stage`
is optional. `scheduled_at` is required and `actual_release_at` is optional:
both must be timezone-aware, and `source_timezone` must be an IANA zone name
(fixed offsets such as `Etc/GMT+5` or `UTC-5` are rejected) so UTC/local views
come from the timezone database and respect DST. Scheduled and actual release
times are never merged: `to_availability_stamp()` builds an
`exact_timestamp` / `official_release_schedule` stamp from the *actual* release
time only and refuses unreleased events. Releases dated on or before the
reference period end (in the source timezone) are rejected.

## ExpectationObservation

```text
release_id
reference_period
expected_value
expectation_type
expectation_source
forecast_created_at
availability: AvailabilityStamp
model_version
source_snapshot_id
```

Implemented in `macrosignal.domain.expectation` (Task 1.6) as three frozen,
distinct types selected by the `expectation_type` discriminator
(`parse_expectation`): `ConsensusExpectation` (`consensus`), `ModelForecast`
(`model_forecast`, additionally requires `model_id`, `model_version`,
`training_cutoff <= forecast_created_at`, optional `input_snapshot_ids`) and
`ProxyExpectation` (`proxy`, requires `proxy_method`). The reference period is
`reference_start` / `reference_end`; `units` is required. `forecast_created_at`
and `availability` are required, timezone-aware, and availability may not precede
creation. `check_pre_release(expectation, release, mode)` enforces the surprise
mode (`market_surprise` accepts only consensus, `forecast_error` only model
forecasts, `proxy_surprise` only proxies), requires availability strictly before
the *actual* release time (and a model's `training_cutoff` strictly before it),
and checks release id / reference period against a `ReleaseEvent`.

## AsOfFeature

```text
feature_name
value
units
available_at
availability_precision
reference_period
age_since_available
age_since_reference
stale
feature_version
input_snapshot_ids
```

## AssetMetadata

```text
asset_id
role
provider
currency
timezone
first_tradable_date
last_tradable_date
coverage_start
price_adjustment_policy
return_convention
```

Implemented as `macrosignal.domain.AssetMetadata` (Task 1.7, frozen, unknown
fields rejected), with an optional `coverage_end`. `provider`, ISO-4217
`currency`, IANA exchange `timezone` (fixed offsets rejected),
`price_adjustment_policy` and `return_convention` are required. Lifecycle rules:
`coverage_start >= first_tradable_date` (no backfill before inception),
`last_tradable_date >= first_tradable_date`, and `coverage_end` within
`coverage_start..last_tradable_date`. `check_observation()` raises
`LifecycleError` when an observation's exchange-local date is outside the
tradable lifecycle or provider coverage, or its asset/provider/currency differ.

## MarketObservation

```text
asset_id
timestamp
field
value
currency
provider
adjustment_policy
retrieved_at
snapshot_id
```

Implemented as `macrosignal.domain.MarketObservation` (Task 1.7). `field` is one
of `open`, `high`, `low`, `close`, `adjusted_close`, `total_return_index`,
`volume`; `adjustment_policy` one of `unadjusted`, `split_adjusted`,
`split_and_dividend_adjusted`, `total_return`, and must be legitimate for the
field (`FIELD_ADJUSTMENTS`, e.g. `adjusted_close` is never `unadjusted`). Prices
must be positive and finite, volume non-negative, timestamps timezone-aware, and
`retrieved_at` not before `timestamp`.

## RegimeStateArtifact

```text
fit_id
raw_state_id
canonical_state_id
probability_type
alignment_confidence
fit_cutoff
model_version
```

## ResearchSnapshot

```text
snapshot_id
as_of
input_snapshot_ids
config_hash
code_commit
created_at
```

## ResearchRun

```text
run_id
snapshot_id
protocol_id
feature_config_hash
regime_config_hash
signal_config_hash
portfolio_config_hash
execution_config_hash
search_registry_id
seed
code_commit
created_at
```

### Manifest implementation (Task 1.9)

`ResearchSnapshot` and `ResearchRun` are implemented in
`macrosignal.domain.manifest` as frozen models. Serialization uses
`canonical_json` (sorted keys, compact separators, UTC ISO-8601 timestamps,
naive datetimes and non-finite floats rejected) and `stable_hash` returns
`sha256:<hex>` of that text. Ids are derived from identity content (everything
except `created_at`): `snap_<20 hex>` from `as_of`, sorted unique
`input_snapshot_ids`, `config_hash` and `code_commit`; `run_<20 hex>` from the
rest of the run manifest. Validators reject ids that do not match content, a
snapshot `created_at` before `as_of`, and non-hex `code_commit` values (an
optional `-dirty` suffix is allowed and visible). A run additionally records
`protocol_version` and embeds every config it used as a `ConfigRecord` (name,
source path, full content, verified hash) in the slots `feature`, `regime`,
`signal`, `portfolio`, `execution`; each `*_config_hash` must equal the embedded
record's hash, so a run is auditable from its manifest alone.
