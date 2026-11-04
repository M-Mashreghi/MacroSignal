"""Yield-curve shape features from available maturities (no silent interpolation).

Each feature is an explicit linear combination of (curve, tenor) yields taken
from the latest curve observation date *knowable* at ``t``:

=====================  =================================================
feature                definition (percent / percentage points)
=====================  =================================================
nominal_level_10y      10Y
nominal_2y             2Y
nominal_spread_10y_2y  10Y - 2Y
nominal_spread_10y_3m  10Y - 3M
nominal_slope_30y_5y   30Y - 5Y
nominal_curvature      2*5Y - 2Y - 10Y  (butterfly)
real_level_10y         real 10Y
breakeven_10y          nominal 10Y - real 10Y (same observation date)
=====================  =================================================

If any required maturity is absent on that date the feature is reported as
missing with the reason; it is never interpolated or taken from another date.
Every feature keeps its observation date, end-of-day availability and the
snapshot ids of its inputs.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict, FiniteFloat

from macrosignal.data.treasury import CurveType, YieldCurveBatch, YieldCurvePoint
from macrosignal.domain import AvailabilityPrecision
from macrosignal.pit.availability_resolver import PRECISION_RANK

CURVE_FEATURE_VERSION = "curve-shape-1"
Leg = tuple[CurveType, str]


@dataclass(frozen=True)
class ShapeSpec:
    name: str
    weights: tuple[tuple[Leg, float], ...]
    units: str


N, R = CurveType.NOMINAL, CurveType.REAL
SHAPE_FEATURES: tuple[ShapeSpec, ...] = (
    ShapeSpec("nominal_level_10y", (((N, "10Y"), 1.0),), "percent"),
    ShapeSpec("nominal_2y", (((N, "2Y"), 1.0),), "percent"),
    ShapeSpec("nominal_spread_10y_2y", (((N, "10Y"), 1.0), ((N, "2Y"), -1.0)), "percentage_points"),
    ShapeSpec("nominal_spread_10y_3m", (((N, "10Y"), 1.0), ((N, "3M"), -1.0)), "percentage_points"),
    ShapeSpec("nominal_slope_30y_5y", (((N, "30Y"), 1.0), ((N, "5Y"), -1.0)), "percentage_points"),
    ShapeSpec(
        "nominal_curvature",
        (((N, "2Y"), -1.0), ((N, "5Y"), 2.0), ((N, "10Y"), -1.0)),
        "percentage_points",
    ),
    ShapeSpec("real_level_10y", (((R, "10Y"), 1.0),), "percent"),
    ShapeSpec("breakeven_10y", (((N, "10Y"), 1.0), ((R, "10Y"), -1.0)), "percentage_points"),
)


class CurveShapeFeature(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_name: str
    as_of: AwareDatetime
    value: FiniteFloat
    units: str
    observation_date: date
    available_at: AwareDatetime
    availability_precision: AvailabilityPrecision
    age_since_available: timedelta
    inputs: tuple[str, ...]
    input_snapshot_ids: tuple[str, ...]
    feature_version: str = CURVE_FEATURE_VERSION


class CurveShapeSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    features: dict[str, CurveShapeFeature]
    missing: dict[str, str]

    def value(self, name: str) -> float | None:
        f = self.features.get(name)
        return None if f is None else f.value


def _latest_points(
    batches: Iterable[YieldCurveBatch], t: datetime
) -> dict[CurveType, dict[str, YieldCurvePoint]]:
    out: dict[CurveType, dict[str, YieldCurvePoint]] = {}
    for batch in batches:
        usable = batch.available_at(t)
        if not usable:
            continue
        day = max(p.observation_date for p in usable)
        out.setdefault(batch.curve, {}).update(
            {p.tenor: p for p in usable if p.observation_date == day}
        )
    return out


def build_curve_shape_features(
    batches: Iterable[YieldCurveBatch],
    as_of: datetime,
    specs: tuple[ShapeSpec, ...] = SHAPE_FEATURES,
) -> CurveShapeSet:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    latest = _latest_points(list(batches), as_of)
    features: dict[str, CurveShapeFeature] = {}
    missing: dict[str, str] = {}
    for spec in specs:
        points: list[YieldCurvePoint] = []
        absent: list[str] = []
        for (curve, tenor), _w in spec.weights:
            p = latest.get(curve, {}).get(tenor)
            if p is None:
                absent.append(f"{curve.value} {tenor}")
            else:
                points.append(p)
        if absent:
            missing[spec.name] = "missing maturities: " + ", ".join(absent)
            continue
        dates = {p.observation_date for p in points}
        if len(dates) > 1:
            missing[spec.name] = "inputs observed on different dates: " + ", ".join(
                sorted(d.isoformat() for d in dates)
            )
            continue
        value = sum(w * p.yield_pct for (_, w), p in zip(spec.weights, points, strict=True))
        available_at = max(p.availability.available_at for p in points)
        features[spec.name] = CurveShapeFeature(
            feature_name=spec.name,
            as_of=as_of,
            value=value,
            units=spec.units,
            observation_date=dates.pop(),
            available_at=available_at,
            availability_precision=max(
                (p.availability.precision for p in points), key=lambda x: PRECISION_RANK[x]
            ),
            age_since_available=as_of - available_at,
            inputs=tuple(f"{c.value}:{t}" for (c, t), _ in spec.weights),
            input_snapshot_ids=tuple(sorted({p.snapshot_id for p in points})),
        )
    return CurveShapeSet(as_of=as_of, features=features, missing=missing)
