"""Transparent rolling-origin pre-release forecast baselines.

For each target release (a :class:`~macrosignal.domain.ReleaseEvent`) a forecast
of the target transformation (e.g. CPI ``mom_pct``) for that reference period is
created at ``creation = actual_release_at - lead`` and trained only on the
series' **as-of view at the creation time**: the realized target is not yet
available, later revisions are not visible, and every training input is checked
with the no-lookahead guard.

Models (deliberately simple and inspectable):

* ``naive``  - last known value;
* ``ar``     - AR(p) with intercept by ordinary least squares;
* ``ridge_ar`` - AR(p) with an L2 penalty ``alpha`` on the lag coefficients.

Each forecast is a :class:`~macrosignal.domain.ModelForecast` (model id,
model version, training cutoff, creation time, availability, input snapshot
ids), wrapped in :class:`BaselineForecast` whose ``label`` is always
``forecast_error`` - a model forecast is never relabelled as a market surprise.
Too little history gives a skipped forecast with a reason, not a fabricated one.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from macrosignal.domain import (
    AvailabilityPrecision,
    AvailabilityStamp,
    ModelForecast,
    ReleaseEvent,
)
from macrosignal.features.series_registry import ResolvedSeries
from macrosignal.features.transformations import transform
from macrosignal.pit.as_of import PitStore, assert_no_lookahead

BASELINE_VERSION = "baseline-1"


@dataclass(frozen=True)
class BaselineModel:
    kind: Literal["naive", "ar", "ridge_ar"]
    lags: int = 1
    alpha: float = 0.0
    min_train: int = 12

    @property
    def model_id(self) -> str:
        if self.kind == "naive":
            return "naive_last"
        if self.kind == "ar":
            return f"ar{self.lags}_ols"
        return f"ridge_ar{self.lags}_a{self.alpha:g}"

    @property
    def model_version(self) -> str:
        return f"{BASELINE_VERSION}:{self.model_id}"

    def fit_predict(self, y: np.ndarray) -> float:
        if self.kind == "naive":
            return float(y[-1])
        p = self.lags
        rows = np.array([y[i - p : i][::-1] for i in range(p, len(y))])
        x = np.column_stack([np.ones(len(rows)), rows])
        target = y[p:]
        if self.kind == "ar":
            beta, *_ = np.linalg.lstsq(x, target, rcond=None)
        else:
            penalty = self.alpha * np.eye(x.shape[1])
            penalty[0, 0] = 0.0  # do not shrink the intercept
            beta = np.linalg.solve(x.T @ x + penalty, x.T @ target)
        latest = np.concatenate([[1.0], y[-p:][::-1]])
        return float(latest @ beta)


class BaselineForecast(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: Literal["forecast_error"] = "forecast_error"
    release_id: str
    target_feature: str
    forecast: ModelForecast | None
    n_train: int
    skipped_reason: str | None = None


def forecast_release(
    store: PitStore,
    series: ResolvedSeries,
    transformation: str,
    release: ReleaseEvent,
    model: BaselineModel,
    *,
    lead: timedelta = timedelta(days=1),
) -> BaselineForecast:
    feature = f"{series.key}__{transformation}"
    if release.actual_release_at is None:
        return BaselineForecast(
            release_id=release.release_id,
            target_feature=feature,
            forecast=None,
            n_train=0,
            skipped_reason="release has no actual release time",
        )
    if release.reference_start is None or release.reference_end is None:
        raise ValueError("forecast targets need a reference period")
    if lead <= timedelta(0):
        raise ValueError("lead must be positive so the forecast precedes the release")
    created = release.actual_release_at - lead
    spec = series.spec
    view = store.as_of(created, series=[(spec.provider, spec.series_id)])
    observations = view.series(spec.provider, spec.series_id)
    assert_no_lookahead(observations, created)
    history = [
        v
        for v in transform(observations, transformation, series_key=series.key)
        if v.reference_start < release.reference_start
    ]
    values = np.array([v.value for v in history], dtype=float)
    needed = max(model.min_train, model.lags + 2 if model.kind != "naive" else 1)
    if len(values) < needed:
        return BaselineForecast(
            release_id=release.release_id,
            target_feature=feature,
            forecast=None,
            n_train=len(values),
            skipped_reason=f"only {len(values)} training values, need {needed}",
        )
    prediction = model.fit_predict(values)
    snapshots = tuple(sorted({s for v in history for s in v.input_snapshot_ids}))
    forecast = ModelForecast(
        release_id=release.release_id,
        reference_start=release.reference_start,
        reference_end=release.reference_end,
        expected_value=prediction,
        units=history[-1].units,
        expectation_source=f"model:{model.model_id}",
        forecast_created_at=created,
        availability=AvailabilityStamp(
            available_at=created, precision=AvailabilityPrecision.EXACT_TIMESTAMP
        ),
        source_snapshot_id=f"{BASELINE_VERSION}:{release.release_id}:{model.model_id}",
        model_id=model.model_id,
        model_version=model.model_version,
        training_cutoff=created,
        input_snapshot_ids=snapshots,
    )
    return BaselineForecast(
        release_id=release.release_id,
        target_feature=feature,
        forecast=forecast,
        n_train=len(values),
    )


def rolling_forecasts(
    store: PitStore,
    series: ResolvedSeries,
    transformation: str,
    releases: Iterable[ReleaseEvent],
    model: BaselineModel,
    *,
    lead: timedelta = timedelta(days=1),
) -> list[BaselineForecast]:
    ordered: Sequence[ReleaseEvent] = sorted(
        releases, key=lambda e: e.actual_release_at or e.scheduled_at
    )
    return [forecast_release(store, series, transformation, e, model, lead=lead) for e in ordered]
