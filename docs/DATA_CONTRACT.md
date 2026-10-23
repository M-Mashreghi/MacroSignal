
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

Implementation status: `macrosignal.domain.availability.AvailabilityStamp`
currently implements `available_at` (timezone-aware) and `precision`, the
subset `MacroObservation` requires (Task 1.4). Task 1.5 adds the remaining
audit fields.

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
