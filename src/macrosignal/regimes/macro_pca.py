"""PCA macro-state baseline with training-only transformations.

A low-dimensional macro state: principal components of the standardized
macro / rates features of an :class:`AsOfFeatureFrame`, fitted on the
complete-case training rows at or before the cutoff (frozen scaler, frozen
loadings).  Signs are fixed deterministically (each component's largest
absolute loading is positive).  Inputs are restricted to macro, rates and
curve-shape cells, so the state is independent of asset returns.

``MacroPcaFit.factor_states(frame)`` applies the frozen transform to every
complete row; rows at or before the cutoff are flagged ``in_sample`` so they
are not mistaken for out-of-sample live states.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict

from macrosignal.domain.manifest import stable_hash
from macrosignal.features.frame import AsOfFeatureFrame, SourceKind
from macrosignal.regimes.training import (
    FrozenScaler,
    TrainingDataError,
    frame_rows,
    training_matrix,
)

MACRO_PCA_VERSION = "macro-pca-1"
ALLOWED_KINDS = frozenset({SourceKind.MACRO, SourceKind.RATES, SourceKind.CURVE_SHAPE})


class MacroFactorState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    fit_id: str
    fit_cutoff: AwareDatetime
    scores: tuple[float, ...]
    in_sample: bool


class MacroPcaFit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_id: str
    features: tuple[str, ...]
    fit_cutoff: AwareDatetime
    train_start: AwareDatetime
    train_end: AwareDatetime
    n_train: int
    n_excluded_incomplete: int
    scaler: FrozenScaler
    loadings: tuple[tuple[float, ...], ...]
    explained_variance_ratio: tuple[float, ...]
    version: str = MACRO_PCA_VERSION

    @property
    def params_hash(self) -> str:
        return stable_hash(self.model_dump(mode="python", exclude={"fit_id"}))

    def transform(self, x: np.ndarray) -> np.ndarray:
        return self.scaler.transform(x) @ np.array(self.loadings).T

    def factor_states(self, frame: AsOfFeatureFrame) -> list[MacroFactorState]:
        times, x, _ = frame_rows(frame, self.features)
        if not times:
            return []
        scores = self.transform(x)
        return [
            MacroFactorState(
                as_of=t,
                fit_id=self.fit_id,
                fit_cutoff=self.fit_cutoff,
                scores=tuple(map(float, s)),
                in_sample=t <= self.fit_cutoff,
            )
            for t, s in zip(times, scores, strict=True)
        ]


def _check_kinds(frame: AsOfFeatureFrame, features: Sequence[str]) -> None:
    for c in frame.cells:
        if c.feature_name in features and c.kind not in ALLOWED_KINDS:
            raise TrainingDataError(
                f"{c.feature_name} is a {c.kind.value} input; macro PCA "
                "uses macro/rates features only"
            )


def fit_macro_pca(
    frame: AsOfFeatureFrame,
    features: Sequence[str],
    cutoff: datetime,
    *,
    n_components: int,
    fit_id: str,
    min_rows: int = 10,
) -> MacroPcaFit:
    if not 1 <= n_components <= len(features):
        raise TrainingDataError("n_components must be between 1 and the number of features")
    _check_kinds(frame, features)
    times, x, excluded = training_matrix(frame, features, cutoff, min_rows=max(min_rows, 2))
    scaler = FrozenScaler.fit(features, x)
    z = scaler.transform(x)
    _, s, vt = np.linalg.svd(z, full_matrices=False)
    comps = vt[:n_components].copy()
    for i in range(n_components):
        if comps[i][np.argmax(np.abs(comps[i]))] < 0:
            comps[i] = -comps[i]
    var = s**2
    return MacroPcaFit(
        fit_id=fit_id,
        features=tuple(features),
        fit_cutoff=cutoff,
        train_start=times[0],
        train_end=times[-1],
        n_train=len(times),
        n_excluded_incomplete=excluded,
        scaler=scaler,
        loadings=tuple(tuple(map(float, r)) for r in comps),
        explained_variance_ratio=tuple(map(float, (var / var.sum())[:n_components])),
    )
