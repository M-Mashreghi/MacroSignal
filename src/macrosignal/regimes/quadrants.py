"""Transparent rule-based growth / inflation macro quadrants.

At each decision time the regime is read off two point-in-time features (one
growth, one inflation) relative to thresholds:

==========================  ===============  ==================
growth vs threshold         inflation        canonical label
==========================  ===============  ==================
above                       below            growth_disinflation
above                       at/above         growth_inflation
at/below                    at/above         slowdown_inflation
at/below                    below            slowdown_disinflation
==========================  ===============  ==================

Thresholds are either ``fixed`` (declared numbers) or statistical
(``expanding_median`` / ``expanding_mean``) computed **only from values seen at
earlier decision times** (each of which was itself point-in-time), with a
declared ``min_history``.  Stale or missing inputs give no label unless the rule
explicitly allows stale inputs.  Every state reports the contributing feature
values, their availability, and the thresholds used.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from statistics import mean, median
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from macrosignal.features.frame import AsOfFeatureFrame, PanelCell


class Quadrant(StrEnum):
    GROWTH_DISINFLATION = "growth_disinflation"
    GROWTH_INFLATION = "growth_inflation"
    SLOWDOWN_INFLATION = "slowdown_inflation"
    SLOWDOWN_DISINFLATION = "slowdown_disinflation"


class QuadrantRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    growth_feature: str
    inflation_feature: str
    threshold_method: Literal["fixed", "expanding_median", "expanding_mean"]
    growth_threshold: float | None = None
    inflation_threshold: float | None = None
    min_history: int = Field(default=12, ge=1)
    allow_stale: bool = False

    @model_validator(mode="after")
    def _check(self) -> QuadrantRule:
        fixed = self.threshold_method == "fixed"
        has = self.growth_threshold is not None and self.inflation_threshold is not None
        if fixed and not has:
            raise ValueError("fixed thresholds require growth_threshold and inflation_threshold")
        if not fixed and (
            self.growth_threshold is not None or self.inflation_threshold is not None
        ):
            raise ValueError("statistical thresholds must not declare fixed values")
        return self


class QuadrantStatus(StrEnum):
    OK = "ok"
    MISSING_INPUT = "missing_input"
    STALE_INPUT = "stale_input"
    INSUFFICIENT_HISTORY = "insufficient_history"


class QuadrantState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    status: QuadrantStatus
    label: Quadrant | None
    growth_feature: str
    inflation_feature: str
    growth_value: float | None
    inflation_value: float | None
    growth_threshold: float | None
    inflation_threshold: float | None
    growth_available_at: AwareDatetime | None
    inflation_available_at: AwareDatetime | None
    n_history: int


def classify(growth: float, inflation: float, g_thr: float, i_thr: float) -> Quadrant:
    if growth > g_thr:
        return Quadrant.GROWTH_DISINFLATION if inflation < i_thr else Quadrant.GROWTH_INFLATION
    return Quadrant.SLOWDOWN_INFLATION if inflation >= i_thr else Quadrant.SLOWDOWN_DISINFLATION


def _threshold(values: Sequence[float], method: str) -> float:
    return float(median(values) if method == "expanding_median" else mean(values))


def classify_frame(frame: AsOfFeatureFrame, rule: QuadrantRule) -> list[QuadrantState]:
    history_g: list[float] = []
    history_i: list[float] = []
    out: list[QuadrantState] = []
    for t in frame.decision_times:
        row = frame.row(t)
        g: PanelCell | None = row.get(rule.growth_feature)
        i: PanelCell | None = row.get(rule.inflation_feature)
        state = _state(t, g, i, rule, history_g, history_i)
        out.append(state)
        # thresholds at later times may use this time's values (they were known at t)
        if g is not None and i is not None:
            history_g.append(g.value)
            history_i.append(i.value)
    return out


def _state(
    t: datetime,
    g: PanelCell | None,
    i: PanelCell | None,
    rule: QuadrantRule,
    history_g: list[float],
    history_i: list[float],
) -> QuadrantState:
    base: dict[str, Any] = {
        "as_of": t,
        "growth_feature": rule.growth_feature,
        "inflation_feature": rule.inflation_feature,
        "growth_value": g.value if g else None,
        "inflation_value": i.value if i else None,
        "growth_available_at": g.available_at if g else None,
        "inflation_available_at": i.available_at if i else None,
        "n_history": len(history_g),
    }
    if g is None or i is None:
        return QuadrantState(
            **base,
            status=QuadrantStatus.MISSING_INPUT,
            label=None,
            growth_threshold=None,
            inflation_threshold=None,
        )
    if not rule.allow_stale and (g.stale or i.stale):
        return QuadrantState(
            **base,
            status=QuadrantStatus.STALE_INPUT,
            label=None,
            growth_threshold=None,
            inflation_threshold=None,
        )
    if rule.threshold_method == "fixed":
        assert rule.growth_threshold is not None and rule.inflation_threshold is not None
        g_thr, i_thr = rule.growth_threshold, rule.inflation_threshold
    else:
        if len(history_g) < rule.min_history:
            return QuadrantState(
                **base,
                status=QuadrantStatus.INSUFFICIENT_HISTORY,
                label=None,
                growth_threshold=None,
                inflation_threshold=None,
            )
        g_thr = _threshold(history_g, rule.threshold_method)
        i_thr = _threshold(history_i, rule.threshold_method)
    return QuadrantState(
        **base,
        status=QuadrantStatus.OK,
        label=classify(g.value, i.value, g_thr, i_thr),
        growth_threshold=g_thr,
        inflation_threshold=i_thr,
    )
