"""Ragged-edge as-of feature panel (``AsOfFeatureFrame``).

A daily (or any decision-time) panel whose cells keep, for every feature at
every decision time: value, ``available_at``, precision, reference period or
observation date, age since availability, age since reference period, stale
flag and source kind.  Cells are computed *as of* each decision time, so a
carried value is the last known state with its **original** availability and
age - forward filling never resets age or hides staleness.

Each cell also carries ``updated_since_previous``: whether its information
became available after the previous decision time (a "fresh release"
indicator), so downstream models and the dashboard can tell a new release
from an old carried value.  Missing features are kept explicit per decision
time.

Feature sources are callables ``t -> (cells, missing)``; adapters are provided
for macro :class:`FeatureSet`, rate features and curve-shape features.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, FiniteFloat

from macrosignal.domain import AvailabilityPrecision
from macrosignal.features.as_of_features import FeatureSet
from macrosignal.features.curve_shape import CurveShapeSet
from macrosignal.features.policy_rates import RateFeature


class SourceKind(StrEnum):
    MACRO = "macro"
    RATES = "rates"
    CURVE_SHAPE = "curve_shape"


class PanelCell(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    feature_name: str
    kind: SourceKind
    value: FiniteFloat
    available_at: AwareDatetime
    availability_precision: AvailabilityPrecision
    reference_start: date | None = None
    reference_end: date | None = None
    observation_date: date | None = None
    age_since_available: timedelta
    age_since_reference_days: int | None = None
    stale: bool
    updated_since_previous: bool = False


FeatureSource = Callable[[datetime], tuple[list[PanelCell], list[str]]]


def cells_from_feature_set(fs: FeatureSet) -> tuple[list[PanelCell], list[str]]:
    cells = [
        PanelCell(
            as_of=f.as_of,
            feature_name=f.feature_name,
            kind=SourceKind.MACRO,
            value=f.value,
            available_at=f.available_at,
            availability_precision=f.availability_precision,
            reference_start=f.reference_start,
            reference_end=f.reference_end,
            age_since_available=f.age_since_available,
            age_since_reference_days=f.age_since_reference_days,
            stale=f.stale,
        )
        for f in fs.features.values()
    ]
    return cells, list(fs.missing)


def cells_from_rates(
    rates: dict[str, RateFeature], missing: Iterable[str] = ()
) -> tuple[list[PanelCell], list[str]]:
    cells = [
        PanelCell(
            as_of=r.as_of,
            feature_name=r.feature_name,
            kind=SourceKind.RATES,
            value=r.value,
            available_at=r.available_at,
            availability_precision=r.availability_precision,
            observation_date=r.observation_date,
            age_since_available=r.age_since_available,
            stale=r.stale,
        )
        for r in rates.values()
    ]
    return cells, list(missing)


def cells_from_curve_shape(
    shapes: CurveShapeSet, stale_after_days: int
) -> tuple[list[PanelCell], list[str]]:
    cells = [
        PanelCell(
            as_of=f.as_of,
            feature_name=f.feature_name,
            kind=SourceKind.CURVE_SHAPE,
            value=f.value,
            available_at=f.available_at,
            availability_precision=f.availability_precision,
            observation_date=f.observation_date,
            age_since_available=f.age_since_available,
            stale=f.age_since_available > timedelta(days=stale_after_days),
        )
        for f in shapes.features.values()
    ]
    return cells, list(shapes.missing)


class AsOfFeatureFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_times: tuple[AwareDatetime, ...]
    cells: tuple[PanelCell, ...]
    missing: dict[str, tuple[str, ...]]  # ISO decision time -> missing feature names

    def row(self, t: datetime) -> dict[str, PanelCell]:
        return {c.feature_name: c for c in self.cells if c.as_of == t}

    def feature(self, name: str) -> list[PanelCell]:
        return [c for c in self.cells if c.feature_name == name]

    @property
    def feature_names(self) -> list[str]:
        return sorted({c.feature_name for c in self.cells})

    def stale_share(self, t: datetime) -> float:
        row = self.row(t)
        return sum(c.stale for c in row.values()) / len(row) if row else 0.0

    def to_records(self) -> list[dict[str, Any]]:
        return [c.model_dump(mode="python") for c in self.cells]

    def to_dataframe(self) -> Any:
        """Long-format pandas DataFrame (one row per decision time and feature)."""
        import pandas as pd  # type: ignore[import-untyped]

        return pd.DataFrame(self.to_records())


def build_feature_frame(
    decision_times: Sequence[datetime], sources: Sequence[FeatureSource]
) -> AsOfFeatureFrame:
    times = list(decision_times)
    for t in times:
        if t.tzinfo is None or t.utcoffset() is None:
            raise ValueError("decision times must be timezone-aware")
    if times != sorted(times) or len(set(times)) != len(times):
        raise ValueError("decision times must be strictly increasing")
    cells: list[PanelCell] = []
    missing: dict[str, tuple[str, ...]] = {}
    previous: datetime | None = None
    for t in times:
        names: set[str] = set()
        miss: list[str] = []
        for source in sources:
            got, m = source(t)
            miss.extend(m)
            for c in got:
                if c.as_of != t:
                    raise ValueError(f"{c.feature_name}: cell computed for a different time")
                if c.available_at > t:
                    raise ValueError(f"{c.feature_name}: available after decision time (lookahead)")
                if c.feature_name in names:
                    raise ValueError(f"duplicate feature {c.feature_name} at {t.isoformat()}")
                names.add(c.feature_name)
                fresh = previous is None or c.available_at > previous
                cells.append(c.model_copy(update={"updated_since_previous": fresh}))
        missing[t.isoformat()] = tuple(sorted(set(miss)))
        previous = t
    return AsOfFeatureFrame(decision_times=tuple(times), cells=tuple(cells), missing=missing)
