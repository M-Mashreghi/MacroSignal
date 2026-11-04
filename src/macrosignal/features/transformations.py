"""Explicit macro transformation registry.

Every transformation declares its formula, lag (in reference periods), the
frequencies it accepts, and its output units.  Transformations are applied to
the observations of *one* series as known at one as-of time, so a YoY value at
time ``t`` uses the vintages of both periods that were knowable at ``t``; its
availability is therefore the later of its two inputs.

=================  ===============================================  ==============
name               formula                                          units
=================  ===============================================  ==============
level              x_t                                              input units
level_diff         x_t - x_{t-1}                                    input units
mom_diff           x_t - x_{t-1}            (monthly)               input units
mom_pct            100 * (x_t / x_{t-1} - 1) (monthly)              percent_mom
qoq_pct            100 * (x_t / x_{t-1} - 1) (quarterly)            percent_qoq
qoq_annualized     100 * ((x_t / x_{t-1})^4 - 1) (quarterly)        percent_annualized
yoy_pct            100 * (x_t / x_{t-k} - 1), k = 12 m / 4 q        percent_yoy
=================  ===============================================  ==============

Gaps are never interpolated: if the lagged period is missing the output is
absent, and percentage changes on a non-positive base are absent too.  Inputs
must share units, frequency and seasonal adjustment, otherwise the conventions
would be mixed silently and the call fails.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, FiniteFloat

from macrosignal.domain import (
    AvailabilityPrecision,
    Frequency,
    MacroObservation,
    ReleaseStage,
    SeasonalAdjustment,
)
from macrosignal.pit.availability_resolver import PRECISION_RANK

FEATURE_VERSION = "transform-1"


class TransformationError(ValueError):
    """Inputs cannot be transformed without mixing conventions."""


@dataclass(frozen=True)
class TransformationSpec:
    name: str
    description: str
    lag: Callable[[Frequency], int]
    frequencies: frozenset[Frequency]
    units: Callable[[str], str]
    compute: Callable[[float, float | None], float | None]


def _pct(cur: float, prev: float | None) -> float | None:
    if prev is None or prev <= 0:
        return None
    return 100.0 * (cur / prev - 1.0)


def _annualized(cur: float, prev: float | None) -> float | None:
    if prev is None or prev <= 0 or cur <= 0:
        return None
    return 100.0 * ((cur / prev) ** 4 - 1.0)


def _diff(cur: float, prev: float | None) -> float | None:
    return None if prev is None else cur - prev


_ALL = frozenset(Frequency)
_MONTHLY = frozenset({Frequency.MONTHLY})
_QUARTERLY = frozenset({Frequency.QUARTERLY})

TRANSFORMATIONS: dict[str, TransformationSpec] = {
    "level": TransformationSpec("level", "x_t", lambda f: 0, _ALL, lambda u: u, lambda c, p: c),
    "level_diff": TransformationSpec(
        "level_diff", "x_t - x_{t-1}", lambda f: 1, _ALL, lambda u: u, _diff
    ),
    "mom_diff": TransformationSpec(
        "mom_diff", "x_t - x_{t-1} (monthly)", lambda f: 1, _MONTHLY, lambda u: u, _diff
    ),
    "mom_pct": TransformationSpec(
        "mom_pct",
        "100*(x_t/x_{t-1}-1) (monthly)",
        lambda f: 1,
        _MONTHLY,
        lambda u: "percent_mom",
        _pct,
    ),
    "qoq_pct": TransformationSpec(
        "qoq_pct",
        "100*(x_t/x_{t-1}-1) (quarterly)",
        lambda f: 1,
        _QUARTERLY,
        lambda u: "percent_qoq",
        _pct,
    ),
    "qoq_annualized": TransformationSpec(
        "qoq_annualized",
        "100*((x_t/x_{t-1})^4-1) (quarterly)",
        lambda f: 1,
        _QUARTERLY,
        lambda u: "percent_annualized",
        _annualized,
    ),
    "yoy_pct": TransformationSpec(
        "yoy_pct",
        "100*(x_t/x_{t-k}-1), k=12 monthly / 4 quarterly",
        lambda f: 12 if f is Frequency.MONTHLY else 4,
        frozenset({Frequency.MONTHLY, Frequency.QUARTERLY}),
        lambda u: "percent_yoy",
        _pct,
    ),
}


class TransformedValue(BaseModel):
    """One transformed value with the provenance needed downstream."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_name: str
    series_key: str
    series_id: str
    transformation: str
    reference_start: date
    reference_end: date
    value: FiniteFloat
    units: str
    seasonal_adjustment: SeasonalAdjustment
    frequency: Frequency
    feature_version: str
    available_at: AwareDatetime
    availability_precision: AvailabilityPrecision
    release_stage: ReleaseStage
    input_snapshot_ids: tuple[str, ...]


def _shift_period(start: date, freq: Frequency, periods: int) -> date:
    months = periods * (1 if freq is Frequency.MONTHLY else 3)
    idx = start.year * 12 + (start.month - 1) - months
    return date(idx // 12, idx % 12 + 1, 1)


def _worst(*precisions: AvailabilityPrecision) -> AvailabilityPrecision:
    return max(precisions, key=lambda p: PRECISION_RANK[p])


def transform(
    observations: Sequence[MacroObservation],
    transformation: str,
    *,
    series_key: str,
    feature_version: str = FEATURE_VERSION,
) -> list[TransformedValue]:
    """Apply ``transformation`` to one series' as-of observations."""
    try:
        spec = TRANSFORMATIONS[transformation]
    except KeyError as exc:
        raise TransformationError(f"unknown transformation {transformation!r}") from exc
    if not observations:
        return []
    first = observations[0]
    for o in observations:
        if (o.source, o.series_id) != (first.source, first.series_id):
            raise TransformationError("observations from several series cannot be mixed")
        for attr in ("units", "frequency", "seasonal_adjustment"):
            if getattr(o, attr) != getattr(first, attr):
                raise TransformationError(
                    f"{first.series_id}: mixed {attr} ({getattr(first, attr)} vs "
                    f"{getattr(o, attr)}); refusing to mix conventions"
                )
    freq = first.frequency
    if freq not in spec.frequencies:
        raise TransformationError(f"{transformation} is not defined for {freq.value} data")
    by_period: dict[date, MacroObservation] = {}
    for o in observations:
        if o.reference_start in by_period:
            raise TransformationError(
                f"{first.series_id}: several vintages for {o.reference_start}; pass one as-of view"
            )
        by_period[o.reference_start] = o

    lag = spec.lag(freq)
    out: list[TransformedValue] = []
    for start in sorted(by_period):
        cur = by_period[start]
        prev = None
        if lag:
            if freq not in (Frequency.MONTHLY, Frequency.QUARTERLY):
                raise TransformationError(f"lagged {transformation} needs monthly/quarterly data")
            prev = by_period.get(_shift_period(start, freq, lag))
            if prev is None:
                continue  # explicit gap: never interpolate
        value = spec.compute(cur.value, None if prev is None else prev.value)
        if value is None:
            continue
        inputs = [cur] if prev is None else [cur, prev]
        available_at: datetime = max(o.availability.available_at for o in inputs)
        out.append(
            TransformedValue(
                feature_name=f"{series_key}__{transformation}",
                series_key=series_key,
                series_id=cur.series_id,
                transformation=transformation,
                reference_start=cur.reference_start,
                reference_end=cur.reference_end,
                value=value,
                units=spec.units(cur.units),
                seasonal_adjustment=cur.seasonal_adjustment,
                frequency=freq,
                feature_version=feature_version,
                available_at=available_at,
                availability_precision=_worst(*(o.availability.precision for o in inputs)),
                release_stage=cur.release_stage,
                input_snapshot_ids=tuple(sorted({o.source_snapshot_id for o in inputs})),
            )
        )
    return out
