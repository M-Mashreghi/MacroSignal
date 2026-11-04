"""Equal-weight & static allocation baselines (Task 5.9)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import CashReturnSpec
from macrosignal.portfolio.allocation import (
    RebalanceSchedule,
    StaticAllocationSpec,
    TargetWeights,
    equal_weight,
    static_allocation,
)
from macrosignal.portfolio.universe import ExclusionReason, TradableUniverse

CASH = CashReturnSpec(mode="zero")
EARLY = TradableUniverse(
    date=date(2003, 1, 2), assets=("SPY", "TLT"), excluded={"GLD": ExclusionReason.BEFORE_INCEPTION}
)
FULL = TradableUniverse(date=date(2010, 1, 4), assets=("SPY", "TLT", "GLD"), excluded={})
SIXTY_FORTY = StaticAllocationSpec(name="60_30_10", weights={"SPY": 0.6, "TLT": 0.3, "GLD": 0.1})


def test_equal_weight_over_tradable_assets() -> None:
    w = equal_weight(EARLY, CASH)
    assert w.weights == {"SPY": 0.5, "TLT": 0.5} and w.cash_weight == 0.0
    assert equal_weight(FULL, CASH).weights["GLD"] == pytest.approx(1 / 3)
    empty = equal_weight(TradableUniverse(date=date(1999, 1, 4), assets=(), excluded={}), CASH)
    assert empty.cash_weight == 1.0 and empty.notes


def test_static_allocation_handles_inception_explicitly() -> None:
    to_cash = static_allocation(EARLY, SIXTY_FORTY, CASH)
    assert to_cash.weights == {"SPY": 0.6, "TLT": 0.3}
    assert to_cash.cash_weight == pytest.approx(0.1)
    assert any("GLD not tradable" in n for n in to_cash.notes)
    renorm = static_allocation(
        EARLY, SIXTY_FORTY.model_copy(update={"unavailable_policy": "renormalize"}), CASH
    )
    assert renorm.weights == pytest.approx({"SPY": 2 / 3, "TLT": 1 / 3})
    assert renorm.cash_weight == pytest.approx(0.0)
    full = static_allocation(FULL, SIXTY_FORTY, CASH)
    assert full.cash_weight == pytest.approx(0.0) and full.method == "static:60_30_10"


def test_partial_static_keeps_explicit_cash() -> None:
    spec = StaticAllocationSpec(name="half", weights={"SPY": 0.5})
    w = static_allocation(FULL, spec, CashReturnSpec(mode="proxy", proxy_series_id="DTB3"))
    assert w.cash_weight == pytest.approx(0.5) and w.cash_policy.proxy_series_id == "DTB3"


def test_rebalance_schedules() -> None:
    cal = UsTradingCalendar()
    monthly = RebalanceSchedule(frequency="monthly").sessions(
        cal, date(2026, 1, 1), date(2026, 4, 30)
    )
    assert monthly == [date(2026, 1, 2), date(2026, 2, 2), date(2026, 3, 2), date(2026, 4, 1)]
    weekly = RebalanceSchedule(frequency="weekly").sessions(
        cal, date(2026, 11, 23), date(2026, 12, 4)
    )
    assert weekly == [date(2026, 11, 23), date(2026, 11, 30)]
    assert (
        len(
            RebalanceSchedule(frequency="daily").sessions(
                cal, date(2026, 11, 23), date(2026, 11, 27)
            )
        )
        == 4
    )


def test_weight_validation() -> None:
    with pytest.raises(ValidationError, match="sum to 1"):
        TargetWeights(
            session=date(2026, 1, 2),
            method="x",
            weights={"SPY": 0.7},
            cash_weight=0.1,
            cash_policy=CASH,
        )
    with pytest.raises(ValidationError, match="exceed 1"):
        StaticAllocationSpec(name="x", weights={"SPY": 0.8, "TLT": 0.4})
    with pytest.raises(ValidationError, match="non-negative"):
        StaticAllocationSpec(name="x", weights={"SPY": -0.1})
