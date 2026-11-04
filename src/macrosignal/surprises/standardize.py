"""Point-in-time surprise standardization and transparent composite factors.

Standardization (per feature and surprise mode, i.e. per release family series):

    z_k = raw_k / scale(raw_j for releases j strictly before release k)

* only *prior* computed surprises enter the scale (expanding window, or the
  last ``window`` releases), so a z-score never uses its own or later releases;
* ``min_history`` prior surprises are required, otherwise the z-score is
  missing (``insufficient_history``);
* ``scale_method`` is ``std`` (sample standard deviation) or ``mad``
  (1.4826 x median absolute deviation, robust to outliers); a zero scale gives
  a missing z-score;
* outlier policy: optional ``winsorize_z`` clips |z| at that bound and flags the
  value as ``clipped`` (the raw surprise is never altered).

Composite factors combine the latest standardized surprise of each member that
is known at ``t`` (and not older than ``max_age_days``) with fixed, declared
weights.  All members must share one surprise mode, so market surprises and
model forecast errors are never mixed, and every composite value lists its
contributing and missing members.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Literal

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.domain import SurpriseMode
from macrosignal.surprises.engine import SurpriseRecord, SurpriseStatus

MAD_TO_SIGMA = 1.4826


class StandardizationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_history: int = Field(ge=2)
    scale_method: Literal["std", "mad"] = "std"
    window: int | None = Field(default=None, ge=2)
    winsorize_z: float | None = Field(default=None, gt=0)
    demean: bool = False


class ZStatus(StrEnum):
    OK = "ok"
    INSUFFICIENT_HISTORY = "insufficient_history"
    ZERO_SCALE = "zero_scale"
    NO_RAW_SURPRISE = "no_raw_surprise"


class StandardizedSurprise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    feature_name: str
    mode: SurpriseMode
    label: str
    release_at: AwareDatetime
    raw_surprise: float | None
    z: float | None
    status: ZStatus
    n_prior: int
    scale: float | None
    center: float | None
    clipped: bool = False
    last_prior_release_id: str | None = None


def _scale(values: np.ndarray, method: str) -> float:
    if method == "mad":
        return float(MAD_TO_SIGMA * np.median(np.abs(values - np.median(values))))
    return float(np.std(values, ddof=1))


def standardize_surprises(
    records: Iterable[SurpriseRecord], policy: StandardizationPolicy
) -> list[StandardizedSurprise]:
    recs = sorted(records, key=lambda r: r.release_at)
    if len({(r.feature_name, r.mode) for r in recs}) > 1:
        raise ValueError("standardize one feature and one surprise mode at a time")
    if len({r.release_id for r in recs}) != len(recs):
        raise ValueError("duplicate release ids")
    out: list[StandardizedSurprise] = []
    for k, rec in enumerate(recs):
        prior = [
            r
            for r in recs[:k]
            if r.status is SurpriseStatus.COMPUTED
            and r.raw_surprise is not None
            and r.release_at < rec.release_at
        ]
        if policy.window is not None:
            prior = prior[-policy.window :]
        base: dict[str, Any] = {
            "release_id": rec.release_id,
            "feature_name": rec.feature_name,
            "mode": rec.mode,
            "label": rec.label,
            "release_at": rec.release_at,
            "raw_surprise": rec.raw_surprise,
            "n_prior": len(prior),
            "last_prior_release_id": prior[-1].release_id if prior else None,
        }
        if rec.raw_surprise is None:
            out.append(
                StandardizedSurprise(
                    **base, z=None, status=ZStatus.NO_RAW_SURPRISE, scale=None, center=None
                )
            )
            continue
        if len(prior) < policy.min_history:
            out.append(
                StandardizedSurprise(
                    **base, z=None, status=ZStatus.INSUFFICIENT_HISTORY, scale=None, center=None
                )
            )
            continue
        values = np.array([r.raw_surprise for r in prior], dtype=float)
        scale = _scale(values, policy.scale_method)
        center = float(np.median(values) if policy.scale_method == "mad" else values.mean())
        if not policy.demean:
            center = 0.0
        if scale <= 0:
            out.append(
                StandardizedSurprise(
                    **base, z=None, status=ZStatus.ZERO_SCALE, scale=scale, center=center
                )
            )
            continue
        z = (rec.raw_surprise - center) / scale
        clipped = False
        if policy.winsorize_z is not None and abs(z) > policy.winsorize_z:
            z = float(np.sign(z) * policy.winsorize_z)
            clipped = True
        out.append(
            StandardizedSurprise(
                **base, z=z, status=ZStatus.OK, scale=scale, center=center, clipped=clipped
            )
        )
    return out


@dataclass(frozen=True)
class CompositeSpec:
    name: str
    members: tuple[tuple[str, float], ...]  # (feature_name, weight)
    mode: SurpriseMode
    max_age_days: int
    min_members: int = 1
    #: Optional orientation per member (+1 / -1), e.g. -1 for unemployment so that a
    #: positive composite always means "stronger than expected". Default +1.
    signs: tuple[tuple[str, int], ...] = ()

    def sign_of(self, feature: str) -> int:
        return dict(self.signs).get(feature, 1)

    def __post_init__(self) -> None:
        names = [m for m, _ in self.members]
        if len(set(names)) != len(names):
            raise ValueError("composite members must be unique")
        if any(w <= 0 for _, w in self.members):
            raise ValueError("composite weights must be positive")
        if not 1 <= self.min_members <= len(self.members):
            raise ValueError("min_members must be between 1 and the number of members")
        for feature, sign in self.signs:
            if feature not in names or sign not in (-1, 1):
                raise ValueError("signs must be +1/-1 for declared members")


class CompositeContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_name: str
    release_id: str
    release_at: AwareDatetime
    z: float
    weight: float
    sign: int = 1


class CompositeValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    mode: SurpriseMode
    as_of: AwareDatetime
    value: float | None
    contributions: tuple[CompositeContribution, ...]
    missing_members: tuple[str, ...]


def composite_as_of(
    spec: CompositeSpec, standardized: Sequence[StandardizedSurprise], as_of: datetime
) -> CompositeValue:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if any(s.mode is not spec.mode for s in standardized):
        raise ValueError(f"composite {spec.name} only accepts {spec.mode.value} inputs")
    contributions: list[CompositeContribution] = []
    missing: list[str] = []
    for feature, weight in spec.members:
        known = [
            s
            for s in standardized
            if s.feature_name == feature and s.release_at <= as_of and s.z is not None
        ]
        latest = max(known, key=lambda s: s.release_at, default=None)
        if latest is None or as_of - latest.release_at > timedelta(days=spec.max_age_days):
            missing.append(feature)
            continue
        assert latest.z is not None
        contributions.append(
            CompositeContribution(
                feature_name=feature,
                release_id=latest.release_id,
                release_at=latest.release_at,
                z=latest.z,
                weight=weight,
                sign=spec.sign_of(feature),
            )
        )
    value = None
    if len(contributions) >= spec.min_members:
        total = sum(c.weight for c in contributions)
        value = sum(c.weight * c.sign * c.z for c in contributions) / total
    return CompositeValue(
        name=spec.name,
        mode=spec.mode,
        as_of=as_of,
        value=value,
        contributions=tuple(contributions),
        missing_members=tuple(missing),
    )
