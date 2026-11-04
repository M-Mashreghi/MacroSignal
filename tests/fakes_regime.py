"""Synthetic two-regime feature frames for regime-model tests (deterministic)."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from macrosignal.features.frame import AsOfFeatureFrame, PanelCell, SourceKind

NY = ZoneInfo("America/New_York")
T0 = datetime(2020, 1, 6, 9, 0, tzinfo=NY)
FEATURES = ("growth", "inflation")

#: Regime centroids in (growth, inflation): 0 = growth/disinflation, 1 = slowdown/inflation.
CENTROIDS = {0: (2.0, -1.5), 1: (-2.0, 1.5)}


def regime_path(n: int, block: int = 15, start: int = 0) -> list[int]:
    """Persistent regimes alternating every ``block`` periods."""
    return [((i // block) + start) % 2 for i in range(n)]


def synthetic_frame(
    n: int = 120,
    *,
    seed: int = 7,
    block: int = 15,
    noise: float = 0.5,
    swap: bool = False,
    step_days: int = 7,
) -> tuple[AsOfFeatureFrame, list[int]]:
    rng = np.random.default_rng(seed)
    states = regime_path(n, block)
    times, cells = [], []
    for k, s in enumerate(states):
        t = T0 + timedelta(days=step_days * k)
        times.append(t)
        c = CENTROIDS[1 - s if swap else s]
        vals = np.array(c) + rng.normal(0, noise, size=2)
        for name, v in zip(FEATURES, vals, strict=True):
            avail = t - timedelta(days=1)
            cells.append(
                PanelCell(
                    as_of=t,
                    feature_name=name,
                    kind=SourceKind.MACRO,
                    value=float(v),
                    available_at=avail,
                    availability_precision="exact_timestamp",
                    age_since_available=t - avail,
                    stale=False,
                )
            )
    return AsOfFeatureFrame(decision_times=tuple(times), cells=tuple(cells), missing={}), states
