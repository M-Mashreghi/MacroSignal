"""Long / flat signal portfolio (Task 5.10)."""

from __future__ import annotations

from datetime import date

import pytest

from macrosignal.domain import CashReturnSpec
from macrosignal.portfolio.long_flat import LongFlatSettings, long_flat_weights
from macrosignal.portfolio.universe import ExclusionReason, TradableUniverse

CASH = CashReturnSpec(mode="zero")
U = TradableUniverse(
    date=date(2026, 6, 1),
    assets=("SPY", "TLT", "GLD", "QQQ"),
    excluded={"USO": ExclusionReason.BEFORE_INCEPTION},
)


def test_negative_scores_go_flat_not_short() -> None:
    w = long_flat_weights(
        {"SPY": 0.6, "TLT": -0.4, "GLD": 0.2}, U, LongFlatSettings(max_weight=1.0), CASH
    )
    assert w.weights == pytest.approx({"GLD": 0.25, "SPY": 0.75})
    assert all(v >= 0 for v in w.weights.values()) and w.cash_weight == pytest.approx(0.0)


def test_caps_leave_excess_in_cash() -> None:
    w = long_flat_weights({"SPY": 0.9, "GLD": 0.1}, U, LongFlatSettings(max_weight=0.4), CASH)
    assert w.weights == pytest.approx({"GLD": 0.1, "SPY": 0.4})
    assert w.cash_weight == pytest.approx(0.5) and any("capped" in n for n in w.notes)
    half = long_flat_weights(
        {"SPY": 1.0, "TLT": 1.0}, U, LongFlatSettings(max_gross=0.5, weighting="equal"), CASH
    )
    assert half.weights == pytest.approx(
        {"SPY": 0.25, "TLT": 0.25}
    ) and half.cash_weight == pytest.approx(0.5)


def test_tradability_and_all_flat() -> None:
    w = long_flat_weights({"USO": 1.0, "SPY": 0.1}, U, LongFlatSettings(max_weight=1.0), CASH)
    assert "USO" not in w.weights and any("non-tradable" in n for n in w.notes)
    flat = long_flat_weights(
        {"SPY": -1.0}, U, LongFlatSettings(), CashReturnSpec(mode="proxy", proxy_series_id="DTB3")
    )
    assert (
        flat.weights == {}
        and flat.cash_weight == 1.0
        and flat.cash_policy.proxy_series_id == "DTB3"
    )
    thresh = long_flat_weights(
        {"SPY": 0.05, "TLT": 0.3}, U, LongFlatSettings(min_score=0.1, max_weight=1), CASH
    )
    assert set(thresh.weights) == {"TLT"}
