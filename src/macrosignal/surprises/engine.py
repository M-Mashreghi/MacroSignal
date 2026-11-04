"""Raw surprise / forecast-error engine.

``actual - expectation`` for one release, one series transformation and one
surprise mode, labelled by where the expectation came from:

==================  =====================  ======================
mode                expectation type       output label
==================  =====================  ======================
market_surprise     consensus              ``market_surprise``
forecast_error      model forecast         ``forecast_error``
proxy_surprise      proxy                  ``proxy_surprise``
==================  =====================  ======================

The **actual** is the value of the release's own stage (the initial print, or
the advance/second/third GDP estimate the event published), transformed from
the as-of view at the moment that vintage became available - never a later
revision.  The expectation comes from :class:`ExpectationService` queried at
the actual release time, so it is necessarily pre-release.

If there is no valid expectation the record has status
``missing_expectation`` and no surprise value; if the actual is not in the
store, ``missing_actual``.  Nothing is imputed.  Units of actual and
expectation must agree.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict

from macrosignal.domain import ExpectationType, MacroObservation, ReleaseEvent, SurpriseMode
from macrosignal.features.series_registry import ResolvedSeries
from macrosignal.features.transformations import transform
from macrosignal.pit.as_of import PitStore
from macrosignal.surprises.expectations import ExpectationService, ExpectationStatus

LABELS: dict[SurpriseMode, str] = {
    SurpriseMode.MARKET_SURPRISE: "market_surprise",
    SurpriseMode.FORECAST_ERROR: "forecast_error",
    SurpriseMode.PROXY_SURPRISE: "proxy_surprise",
}


class SurpriseStatus(StrEnum):
    COMPUTED = "computed"
    MISSING_EXPECTATION = "missing_expectation"
    MISSING_ACTUAL = "missing_actual"


class SurpriseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    release_family: str
    series_key: str
    feature_name: str
    mode: SurpriseMode
    label: str
    expectation_type: ExpectationType
    status: SurpriseStatus
    release_at: AwareDatetime
    actual: float | None = None
    actual_available_at: AwareDatetime | None = None
    actual_stage: str | None = None
    expected: float | None = None
    expectation_provider: str | None = None
    expectation_available_at: AwareDatetime | None = None
    raw_surprise: float | None = None
    units: str | None = None


class UnitsMismatchError(ValueError):
    """Actual and expectation are in different units."""


def release_actual(
    store: PitStore, series: ResolvedSeries, transformation: str, release: ReleaseEvent
) -> tuple[float, MacroObservation, str] | None:
    """(transformed actual, published observation, units) for the release's own stage."""
    if release.reference_start is None or release.release_stage is None:
        raise ValueError("surprises need a release with a reference period and stage")
    spec = series.spec
    chain = store.vintages(spec.provider, spec.series_id, release.reference_start)
    matching = [
        o for o in chain if series.mapping.canonical_stage(o.release_stage) == release.release_stage
    ]
    if not matching:
        return None
    published = min(matching, key=lambda o: o.availability.available_at)
    moment = published.availability.available_at
    view = store.as_of(moment, series=[(spec.provider, spec.series_id)])
    values = [
        v
        for v in transform(
            view.series(spec.provider, spec.series_id), transformation, series_key=series.key
        )
        if v.reference_start == release.reference_start
    ]
    if not values:
        return None
    return values[0].value, published, values[0].units


def compute_surprise(
    store: PitStore,
    series: ResolvedSeries,
    transformation: str,
    release: ReleaseEvent,
    service: ExpectationService,
    mode: SurpriseMode,
) -> SurpriseRecord:
    if release.actual_release_at is None:
        raise ValueError(f"{release.release_id} has no actual release time")
    if series.mapping.release_family != release.release_family:
        raise ValueError(
            f"{series.key} belongs to {series.mapping.release_family}, not {release.release_family}"
        )
    base: dict[str, Any] = {
        "release_id": release.release_id,
        "release_family": release.release_family,
        "series_key": series.key,
        "feature_name": f"{series.key}__{transformation}",
        "mode": mode,
        "label": LABELS[mode],
        "release_at": release.actual_release_at,
    }
    expectation = service.get(release, mode, release.actual_release_at)
    actual = release_actual(store, series, transformation, release)
    if actual is None:
        return SurpriseRecord(
            **base,
            expectation_type=expectation.expectation_type,
            status=SurpriseStatus.MISSING_ACTUAL,
        )
    value, published, units = actual
    common: dict[str, Any] = {
        **base,
        "expectation_type": expectation.expectation_type,
        "actual": value,
        "actual_available_at": published.availability.available_at,
        "actual_stage": published.release_stage.value,
        "units": units,
    }
    if expectation.status is ExpectationStatus.MISSING or expectation.expectation is None:
        return SurpriseRecord(**common, status=SurpriseStatus.MISSING_EXPECTATION)
    exp = expectation.expectation
    if exp.units != units:
        raise UnitsMismatchError(
            f"{release.release_id}: actual in {units!r} but expectation in {exp.units!r}"
        )
    return SurpriseRecord(
        **common,
        status=SurpriseStatus.COMPUTED,
        expected=exp.expected_value,
        expectation_provider=expectation.provider,
        expectation_available_at=exp.availability.available_at,
        raw_surprise=value - exp.expected_value,
    )
