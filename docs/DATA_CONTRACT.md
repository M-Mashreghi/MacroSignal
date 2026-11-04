
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
