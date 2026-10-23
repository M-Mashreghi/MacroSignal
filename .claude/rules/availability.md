
# Availability Rules

Availability is a first-class property.

Store:
- available_at,
- precision,
- source of availability,
- whether timestamp is exact or inferred.

Precision values:
- exact_timestamp
- provider_timestamp
- release_date_only
- inferred_eod
- unknown

Do not upgrade a date-only vintage to an exact timestamp without a documented
release-calendar mapping.

When availability precision is insufficient for an experiment, exclude the
observation or use a conservative timestamp.
