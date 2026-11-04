"""Training-only yield-curve PCA with frozen parameters.

``fit_curve_pca`` uses only curve rows whose availability is at or before the
training cutoff (and that have every requested tenor - incomplete dates are
excluded and counted, never imputed).  It standardizes each tenor with the
training mean and population standard deviation, takes principal components by
SVD, fixes signs deterministically (component 1: positive loading sum, i.e. a
"level" factor rises with yields; later components: positive loading on the
longest tenor), and freezes everything in :class:`FrozenCurvePCA`.

``FrozenCurvePCA.transform`` applies the frozen means, scales and loadings to
any later curve; nothing about it can change when future data arrive.  Fitting
on a store that already contains future rows gives exactly the same parameters
as fitting on the past alone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.data.treasury import CurveType, YieldCurveBatch
from macrosignal.domain.manifest import stable_hash

PCA_VERSION = "curve-pca-1"


class CurvePCAError(ValueError):
    """Not enough clean training data, or inputs incompatible with the frozen fit."""


class FrozenCurvePCA(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_id: str
    curve: CurveType
    tenors: tuple[str, ...]
    train_cutoff: AwareDatetime
    train_start: date
    train_end: date
    n_train: int = Field(ge=2)
    n_excluded_incomplete: int = Field(ge=0)
    means: tuple[float, ...]
    scales: tuple[float, ...]
    loadings: tuple[tuple[float, ...], ...]
    explained_variance_ratio: tuple[float, ...]
    version: str = PCA_VERSION

    @property
    def params_hash(self) -> str:
        return stable_hash(self.model_dump(mode="python", exclude={"fit_id"}))

    @property
    def n_components(self) -> int:
        return len(self.loadings)

    def transform(self, yields: Mapping[str, float]) -> tuple[float, ...]:
        missing = [t for t in self.tenors if t not in yields]
        if missing:
            raise CurvePCAError(f"missing tenors {missing}; frozen PCA does not impute")
        x = np.array([yields[t] for t in self.tenors], dtype=float)
        z = (x - np.array(self.means)) / np.array(self.scales)
        scores = np.array(self.loadings) @ z
        return tuple(float(s) for s in scores)


def training_matrix(
    batches: Iterable[YieldCurveBatch],
    curve: CurveType,
    tenors: Sequence[str],
    train_cutoff: datetime,
) -> tuple[list[date], np.ndarray, int]:
    """Complete-case rows (dates x tenors) available by ``train_cutoff``."""
    by_date: dict[date, dict[str, float]] = {}
    for batch in batches:
        if batch.curve is not curve:
            continue
        for p in batch.available_at(train_cutoff):
            by_date.setdefault(p.observation_date, {})[p.tenor] = p.yield_pct
    dates = sorted(by_date)
    complete = [d for d in dates if all(t in by_date[d] for t in tenors)]
    excluded = len(dates) - len(complete)
    matrix = np.array([[by_date[d][t] for t in tenors] for d in complete], dtype=float)
    return complete, matrix, excluded


def fit_curve_pca(
    batches: Iterable[YieldCurveBatch],
    *,
    curve: CurveType,
    tenors: Sequence[str],
    train_cutoff: datetime,
    n_components: int,
    fit_id: str,
    min_rows: int = 2,
) -> FrozenCurvePCA:
    if train_cutoff.tzinfo is None or train_cutoff.utcoffset() is None:
        raise CurvePCAError("train_cutoff must be timezone-aware")
    if not 1 <= n_components <= len(tenors):
        raise CurvePCAError("n_components must be between 1 and the number of tenors")
    dates, x, excluded = training_matrix(list(batches), curve, tenors, train_cutoff)
    if len(dates) < max(min_rows, 2):
        raise CurvePCAError(f"only {len(dates)} complete training rows before the cutoff")
    means = x.mean(axis=0)
    scales = x.std(axis=0, ddof=0)
    if np.any(scales == 0):
        flat = [t for t, s in zip(tenors, scales, strict=True) if s == 0]
        raise CurvePCAError(f"zero training variance for tenors {flat}")
    z = (x - means) / scales
    _, s, vt = np.linalg.svd(z, full_matrices=False)
    var = s**2
    ratio = var / var.sum()
    comps = vt[:n_components].copy()
    for i in range(n_components):
        anchor = comps[i].sum() if i == 0 else comps[i][-1]
        if anchor < 0:
            comps[i] = -comps[i]
    return FrozenCurvePCA(
        fit_id=fit_id,
        curve=curve,
        tenors=tuple(tenors),
        train_cutoff=train_cutoff,
        train_start=dates[0],
        train_end=dates[-1],
        n_train=len(dates),
        n_excluded_incomplete=excluded,
        means=tuple(float(v) for v in means),
        scales=tuple(float(v) for v in scales),
        loadings=tuple(tuple(float(v) for v in row) for row in comps),
        explained_variance_ratio=tuple(float(v) for v in ratio[:n_components]),
    )
