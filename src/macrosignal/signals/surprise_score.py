"""Surprise / forecast-error asset scores with age decay.

``score_a(t) = sum_f beta[f, a] * z_f * decay(age_f)`` where, for each factor
``f`` (a standardized surprise feature or a composite), only its **latest**
value released at or before ``t`` is used - a newer release replaces the older
one instead of adding to it - and

``decay(age) = 0.5 ** (age_days / half_life_days)`` for ``age <= max_age_days``,
else 0 (the release no longer influences the signal).

The decay parameters come from the signal config
(``surprise_component.decay``: ``type: exponential``,
``default_half_life_days``, ``max_age_days``).  All inputs must share one
surprise mode, which labels the output (``market_surprise`` or
``forecast_error`` scores are never mixed).  Factors without a usable value are
listed as missing (contribution 0, never imputed), and each score carries its
per-factor decomposition with the release id and age used.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.config.models import SignalDecaySpec
from macrosignal.domain import SurpriseMode
from macrosignal.surprises.standardize import StandardizedSurprise


class SurpriseSensitivityMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    map_id: str
    betas: dict[str, dict[str, float]]  # factor feature name -> asset -> sensitivity


class DecayPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    half_life_days: float = Field(gt=0)
    max_age_days: int = Field(gt=0)

    @classmethod
    def from_config(cls, spec: SignalDecaySpec) -> DecayPolicy:
        if spec.type != "exponential":
            raise ValueError(f"unsupported decay type {spec.type!r}")
        return cls(half_life_days=spec.default_half_life_days, max_age_days=spec.max_age_days)

    def factor(self, age_days: float) -> float:
        if age_days < 0:
            raise ValueError("negative age: release after decision time")
        if age_days > self.max_age_days:
            return 0.0
        return float(0.5 ** (age_days / self.half_life_days))


class FactorContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    factor: str
    release_id: str
    age_days: float
    z: float
    decay: float
    beta: float
    contribution: float


class SurpriseAssetScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    asset_id: str
    mode: SurpriseMode
    label: str
    score: float
    contributions: tuple[FactorContribution, ...]
    missing_factors: tuple[str, ...]
    map_id: str


def surprise_scores(
    standardized: Sequence[StandardizedSurprise],
    sensitivities: SurpriseSensitivityMap,
    decay: DecayPolicy,
    as_of: datetime,
    assets: Sequence[str],
    mode: SurpriseMode,
) -> dict[str, SurpriseAssetScore]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if any(s.mode is not mode for s in standardized):
        raise ValueError(f"surprise scores for {mode.value} cannot use other surprise modes")
    latest: dict[str, StandardizedSurprise] = {}
    for s in standardized:
        if s.release_at > as_of:
            continue
        cur = latest.get(s.feature_name)
        if cur is None or s.release_at > cur.release_at:
            latest[s.feature_name] = s  # newer release replaces the previous one
    active: dict[str, tuple[StandardizedSurprise, float, float]] = {}
    missing: list[str] = []
    for factor in sorted(sensitivities.betas):
        found = latest.get(factor)
        if found is None or found.z is None:
            missing.append(factor)
            continue
        age = (as_of - found.release_at).total_seconds() / 86400
        d = decay.factor(age)
        if d == 0.0:
            missing.append(factor)
            continue
        active[factor] = (found, age, d)
    label = {
        SurpriseMode.MARKET_SURPRISE: "market_surprise",
        SurpriseMode.FORECAST_ERROR: "forecast_error",
        SurpriseMode.PROXY_SURPRISE: "proxy_surprise",
    }[mode]
    out: dict[str, SurpriseAssetScore] = {}
    for asset in assets:
        parts: list[FactorContribution] = []
        for factor, (s, age, d) in active.items():
            beta = sensitivities.betas[factor].get(asset, 0.0)
            assert s.z is not None
            parts.append(
                FactorContribution(
                    factor=factor,
                    release_id=s.release_id,
                    age_days=age,
                    z=s.z,
                    decay=d,
                    beta=beta,
                    contribution=beta * s.z * d,
                )
            )
        out[asset] = SurpriseAssetScore(
            as_of=as_of,
            asset_id=asset,
            mode=mode,
            label=label,
            score=sum(p.contribution for p in parts),
            contributions=tuple(parts),
            missing_factors=tuple(missing),
            map_id=sensitivities.map_id,
        )
    return out


def scores_by_asset(scores: Mapping[str, SurpriseAssetScore]) -> dict[str, float]:
    return {a: s.score for a, s in scores.items()}
