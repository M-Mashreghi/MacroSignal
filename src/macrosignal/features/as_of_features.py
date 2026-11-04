"""Release-aware as-of feature computation with age and staleness metadata.

For a decision time ``t`` and a family of configured series, every configured
transformation is computed from the series' *as-of view at t* (only vintages
available by ``t``; Task 2.12) and the most recent reference period that has a
value becomes an :class:`AsOfFeature`.  Each feature carries:

* value, units, seasonal adjustment, transformation and feature version;
* reference period and release stage of the latest input;
* ``available_at`` (the later of the transformation's inputs) and its precision;
* ``age_since_available`` and ``age_since_reference_days``;
* ``stale`` - ``age_since_reference_days > stale_after_days`` (the threshold is
  per series in the registry config, never hidden in code);
* input snapshot ids.

Features that cannot be computed at ``t`` (no data yet, or a gap) are listed in
``missing`` rather than filled.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, FiniteFloat, model_validator

from macrosignal.domain import AvailabilityPrecision, ReleaseStage, SeasonalAdjustment
from macrosignal.features.series_registry import ResolvedSeries, SeriesCatalog
from macrosignal.features.transformations import FEATURE_VERSION, transform
from macrosignal.pit.as_of import PitStore

AGE_TIMEZONE = ZoneInfo("America/New_York")


class AsOfFeature(BaseModel):
    """One feature value as known at ``as_of`` (docs/RAGGED_EDGE_POLICY.md)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_name: str
    family: str
    series_key: str
    transformation: str
    as_of: AwareDatetime
    value: FiniteFloat
    units: str
    seasonal_adjustment: SeasonalAdjustment
    reference_start: date
    reference_end: date
    release_stage: ReleaseStage
    available_at: AwareDatetime
    availability_precision: AvailabilityPrecision
    age_since_available: timedelta
    age_since_reference_days: int
    stale_after_days: int
    stale: bool
    feature_version: str
    input_snapshot_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _check(self) -> AsOfFeature:
        if self.available_at > self.as_of:
            raise ValueError(f"{self.feature_name}: available_at is after as_of (lookahead)")
        if self.age_since_available != self.as_of - self.available_at:
            raise ValueError("age_since_available must equal as_of - available_at")
        if self.stale != (self.age_since_reference_days > self.stale_after_days):
            raise ValueError("stale flag inconsistent with reference age and threshold")
        return self


class FeatureSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    family: str
    as_of: AwareDatetime
    features: dict[str, AsOfFeature]
    missing: tuple[str, ...]

    def value(self, name: str) -> float | None:
        f = self.features.get(name)
        return None if f is None else f.value

    @property
    def stale_features(self) -> list[str]:
        return sorted(n for n, f in self.features.items() if f.stale)


def _reference_age_days(as_of: datetime, reference_end: date) -> int:
    return (as_of.astimezone(AGE_TIMEZONE).date() - reference_end).days


def series_features(
    store: PitStore,
    series: ResolvedSeries,
    as_of: datetime,
    *,
    feature_version: str = FEATURE_VERSION,
) -> tuple[list[AsOfFeature], list[str]]:
    spec = series.spec
    view = store.as_of(as_of, series=[(spec.provider, spec.series_id)])
    observations = view.series(spec.provider, spec.series_id)
    features: list[AsOfFeature] = []
    missing: list[str] = []
    for name in spec.transformation_set:
        feature_name = f"{spec.key}__{name}"
        values = transform(observations, name, series_key=spec.key, feature_version=feature_version)
        if not values:
            missing.append(feature_name)
            continue
        latest = values[-1]
        if observations and latest.reference_start != observations[-1].reference_start:
            # The newest period exists but its transformation has a gap: do not fall back
            # silently to an older period; report the feature as missing.
            missing.append(feature_name)
            continue
        ref_age = _reference_age_days(as_of, latest.reference_end)
        features.append(
            AsOfFeature(
                feature_name=feature_name,
                family=spec.family,
                series_key=spec.key,
                transformation=name,
                as_of=as_of,
                value=latest.value,
                units=latest.units,
                seasonal_adjustment=latest.seasonal_adjustment,
                reference_start=latest.reference_start,
                reference_end=latest.reference_end,
                release_stage=latest.release_stage,
                available_at=latest.available_at,
                availability_precision=latest.availability_precision,
                age_since_available=as_of - latest.available_at,
                age_since_reference_days=ref_age,
                stale_after_days=spec.stale_after_days,
                stale=ref_age > spec.stale_after_days,
                feature_version=feature_version,
                input_snapshot_ids=latest.input_snapshot_ids,
            )
        )
    return features, missing


def build_family_features(
    store: PitStore,
    catalog: SeriesCatalog,
    family: str,
    as_of: datetime,
    *,
    series_keys: Sequence[str] | None = None,
) -> FeatureSet:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    members = catalog.by_family(family)
    if series_keys is not None:
        members = [s for s in members if s.key in set(series_keys)]
    if not members:
        raise ValueError(f"no configured series in family {family!r}")
    features: dict[str, AsOfFeature] = {}
    missing: list[str] = []
    for s in members:
        got, miss = series_features(store, s, as_of)
        features.update({f.feature_name: f for f in got})
        missing.extend(miss)
    return FeatureSet(family=family, as_of=as_of, features=features, missing=tuple(sorted(missing)))
