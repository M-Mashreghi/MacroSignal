"""Training-window feature matrices and frozen scalers for latent regime models.

``training_matrix`` takes an :class:`AsOfFeatureFrame` and returns the
complete-case rows (decision times x features) with decision time at or before
the training cutoff.  Each row was computed point-in-time, so the matrix never
contains information unavailable at its own decision time, and rows after the
cutoff never enter a fit.  Incomplete rows are excluded and counted, never
imputed.

``FrozenScaler`` stores training means and population standard deviations; it is
applied unchanged to later rows.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import numpy as np
from pydantic import BaseModel, ConfigDict

from macrosignal.features.frame import AsOfFeatureFrame


class TrainingDataError(ValueError):
    """Not enough clean training rows."""


class FrozenScaler(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    features: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]

    @classmethod
    def fit(cls, features: Sequence[str], x: np.ndarray) -> FrozenScaler:
        scales = x.std(axis=0, ddof=0)
        if np.any(scales == 0):
            flat = [f for f, s in zip(features, scales, strict=True) if s == 0]
            raise TrainingDataError(f"zero training variance for {flat}")
        return cls(
            features=tuple(features),
            means=tuple(map(float, x.mean(axis=0))),
            scales=tuple(map(float, scales)),
        )

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (np.asarray(x, dtype=float) - np.array(self.means)) / np.array(self.scales)


def frame_rows(
    frame: AsOfFeatureFrame, features: Sequence[str], *, until: datetime | None = None
) -> tuple[list[datetime], np.ndarray, int]:
    """Complete-case rows of ``features`` (optionally only decision times <= ``until``)."""
    times: list[datetime] = []
    rows: list[list[float]] = []
    excluded = 0
    for t in frame.decision_times:
        if until is not None and t > until:
            continue
        row = frame.row(t)
        if all(f in row for f in features):
            times.append(t)
            rows.append([row[f].value for f in features])
        else:
            excluded += 1
    return times, np.array(rows, dtype=float).reshape(len(rows), len(features)), excluded


def training_matrix(
    frame: AsOfFeatureFrame, features: Sequence[str], cutoff: datetime, *, min_rows: int
) -> tuple[list[datetime], np.ndarray, int]:
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise TrainingDataError("training cutoff must be timezone-aware")
    times, x, excluded = frame_rows(frame, features, until=cutoff)
    if len(times) < min_rows:
        raise TrainingDataError(f"only {len(times)} complete training rows before the cutoff")
    return times, x, excluded
