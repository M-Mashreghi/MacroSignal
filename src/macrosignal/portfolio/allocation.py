"""Target-weight model, rebalance schedules and benchmark allocations.

:class:`TargetWeights` is the common output of every portfolio method: weights
per tradable asset for one rebalance session, the explicit cash weight, the
cash policy that cash earns, the method and notes.

Baselines on the as-of tradable universe (Task 5.1):

* :func:`equal_weight` - ``1/N`` across the assets tradable on the date;
* :func:`static_allocation` - declared weights; weights of assets that are not
  yet tradable (before inception / outside coverage) follow an explicit
  ``unavailable_policy``: ``to_cash`` (default, keeps the other weights) or
  ``renormalize`` (scales the available weights up).

:class:`RebalanceSchedule` lists rebalance sessions (``daily``, ``weekly`` =
first session of each ISO week, ``monthly`` = first session of each month) on
the trading calendar.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import CashReturnSpec
from macrosignal.portfolio.universe import TradableUniverse

WEIGHT_TOLERANCE = 1e-9


class TargetWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session: date
    method: str
    weights: dict[str, float]
    cash_weight: float
    cash_policy: CashReturnSpec
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> TargetWeights:
        values = [*self.weights.values(), self.cash_weight]
        if not all(math.isfinite(v) for v in values):
            raise ValueError("weights must be finite")
        if abs(sum(values) - 1.0) > 1e-6:
            raise ValueError("asset weights plus cash must sum to 1")
        return self

    @property
    def gross_exposure(self) -> float:
        return sum(abs(w) for w in self.weights.values())


class RebalanceSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    frequency: Literal["daily", "weekly", "monthly"]

    def sessions(self, calendar: UsTradingCalendar, start: date, end: date) -> list[date]:
        days = calendar.sessions(start, end)
        if self.frequency == "daily":
            return days
        out: list[date] = []
        seen: set[tuple[int, int]] = set()
        for d in days:
            key = (
                (d.isocalendar()[0], d.isocalendar()[1])
                if self.frequency == "weekly"
                else (d.year, d.month)
            )
            if key not in seen:
                seen.add(key)
                out.append(d)
        return out


def equal_weight(universe: TradableUniverse, cash_policy: CashReturnSpec) -> TargetWeights:
    n = len(universe.assets)
    if n == 0:
        return TargetWeights(
            session=universe.date,
            method="equal_weight",
            weights={},
            cash_weight=1.0,
            cash_policy=cash_policy,
            notes=("no tradable assets; fully in cash",),
        )
    w = 1.0 / n
    return TargetWeights(
        session=universe.date,
        method="equal_weight",
        weights={a: w for a in universe.assets},
        cash_weight=0.0,
        cash_policy=cash_policy,
    )


class StaticAllocationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    weights: dict[str, float] = Field(min_length=1)
    unavailable_policy: Literal["to_cash", "renormalize"] = "to_cash"

    @model_validator(mode="after")
    def _check(self) -> StaticAllocationSpec:
        if any(w < 0 for w in self.weights.values()):
            raise ValueError("static allocation weights must be non-negative")
        if sum(self.weights.values()) > 1.0 + WEIGHT_TOLERANCE:
            raise ValueError("static allocation weights must not exceed 1")
        return self


def static_allocation(
    universe: TradableUniverse, spec: StaticAllocationSpec, cash_policy: CashReturnSpec
) -> TargetWeights:
    available = {a: w for a, w in spec.weights.items() if a in universe.assets}
    unavailable = sorted(set(spec.weights) - set(available))
    notes = [
        f"{a} not tradable on {universe.date} ({universe.excluded.get(a, 'not configured')})"
        for a in unavailable
    ]
    if spec.unavailable_policy == "renormalize" and available:
        target_total = sum(spec.weights.values())
        scale = target_total / sum(available.values()) if sum(available.values()) > 0 else 0.0
        weights = {a: w * scale for a, w in available.items()}
        if unavailable:
            notes.append("unavailable weight redistributed pro rata")
    else:
        weights = dict(available)
        if unavailable:
            notes.append("unavailable weight held in cash")
    cash = 1.0 - sum(weights.values())
    return TargetWeights(
        session=universe.date,
        method=f"static:{spec.name}",
        weights=weights,
        cash_weight=cash,
        cash_policy=cash_policy,
        notes=tuple(notes),
    )


def weights_dict(weights: TargetWeights) -> Mapping[str, float]:
    return {**weights.weights, "CASH": weights.cash_weight}
