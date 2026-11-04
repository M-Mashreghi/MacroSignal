"""Labor feature pipeline: payrolls and unemployment on Employment Situation timing.

Labor series must belong to the ``EMPLOYMENT_SITUATION`` release family with
``release_calendar`` timing, so availability can be resolved to the official
release time.  Features are computed from the as-of view, which is
revision-aware: at each Employment Situation release the newly published
vintages of earlier months (payroll revisions) replace older ones *from that
release onwards only*.

Freshness: besides each feature's own age, :class:`LaborFeatureSet` reports the
latest Employment Situation release known at ``t`` (from the calendar) and the
features that are *overdue* - a release happened after their last update but
no corresponding data are in the store - so a missing update is visible
instead of silently carrying an old value.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from macrosignal.domain import ReleaseEvent
from macrosignal.features.as_of_features import FeatureSet, build_family_features
from macrosignal.features.series_registry import SeriesCatalog
from macrosignal.pit.as_of import PitStore

LABOR_FAMILY = "labor"
LABOR_RELEASE_FAMILY = "EMPLOYMENT_SITUATION"


class LaborFeatureSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    features: FeatureSet
    latest_release: ReleaseEvent | None
    overdue_features: tuple[str, ...]

    def value(self, name: str) -> float | None:
        return self.features.value(name)


def _check_catalog(catalog: SeriesCatalog) -> None:
    for s in catalog.by_family(LABOR_FAMILY):
        if s.mapping.release_family != LABOR_RELEASE_FAMILY:
            raise ValueError(
                f"labor series {s.key} must use the {LABOR_RELEASE_FAMILY} release family"
            )
        if s.spec.timing_policy != "release_calendar":
            raise ValueError(f"labor series {s.key} must use release_calendar timing")


def build_labor_features(
    store: PitStore,
    catalog: SeriesCatalog,
    as_of: datetime,
    release_events: Iterable[ReleaseEvent] = (),
) -> LaborFeatureSet:
    _check_catalog(catalog)
    features = build_family_features(store, catalog, LABOR_FAMILY, as_of)
    released = [
        e
        for e in release_events
        if e.release_family == LABOR_RELEASE_FAMILY
        and e.actual_release_at is not None
        and e.actual_release_at <= as_of
    ]
    latest = max(released, key=lambda e: e.actual_release_at or as_of, default=None)
    overdue: list[str] = []
    if latest is not None and latest.actual_release_at is not None:
        for name, f in features.features.items():
            if f.available_at < latest.actual_release_at:
                overdue.append(name)
        overdue.extend(features.missing)
    return LaborFeatureSet(
        features=features, latest_release=latest, overdue_features=tuple(sorted(set(overdue)))
    )
