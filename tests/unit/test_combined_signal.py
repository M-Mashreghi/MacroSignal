"""Combined transparent signal model (Task 5.8)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from macrosignal.domain import SurpriseMode
from macrosignal.signals.combined import (
    ComponentWeights,
    SelectionRow,
    combine,
    decomposition_json,
    select_weights,
)
from macrosignal.signals.regime_score import RegimeAssetScore
from macrosignal.signals.surprise_score import SurpriseAssetScore
from macrosignal.signals.trend import TrendSignal, TrendStatus

NY = ZoneInfo("America/New_York")
T = datetime(2026, 6, 1, 9, 0, tzinfo=NY)


def _r(asset: str, s: float) -> RegimeAssetScore:
    return RegimeAssetScore(
        as_of=T,
        asset_id=asset,
        score=s,
        raw_score=s,
        confidence_weight=1.0,
        decomposition={},
        map_id="m",
        regime_fit_id="f",
    )


def _s(asset: str, s: float) -> SurpriseAssetScore:
    return SurpriseAssetScore(
        as_of=T,
        asset_id=asset,
        mode=SurpriseMode.MARKET_SURPRISE,
        label="market_surprise",
        score=s,
        contributions=(),
        missing_factors=(),
        map_id="b",
    )


def _t(asset: str, d: int | None) -> TrendSignal:
    return TrendSignal(
        asset_id=asset,
        decision_session=date(2026, 6, 1),
        status=TrendStatus.OK if d is not None else TrendStatus.MISSING,
        direction=d,
        lookback_days=60,
    )


def test_combination_and_decomposition() -> None:
    w = ComponentWeights(regime=0.5, surprise=0.3, trend=0.2)
    out = combine(
        T,
        ["SPY", "TLT"],
        w,
        {"SPY": _r("SPY", 0.6), "TLT": _r("TLT", -0.6)},
        {"SPY": _s("SPY", -1.0)},
        {"SPY": _t("SPY", 1), "TLT": _t("TLT", None)},
    )
    assert out["SPY"].total == pytest.approx(0.5 * 0.6 - 0.3 + 0.2)
    assert out["SPY"].weighted["surprise"] == pytest.approx(-0.3)
    assert out["TLT"].missing_components == ("surprise", "trend")
    rows = json.loads(decomposition_json(out))
    assert rows[0]["asset_id"] == "SPY" and rows[0]["regime_score"] == 0.6


def _rows(n: int) -> list[SelectionRow]:
    rows = []
    for i in range(n):
        t = T + timedelta(days=7 * i)
        sign = 1 if i % 2 else -1
        rows.append(
            SelectionRow(
                as_of=t,
                forward_end=t + timedelta(days=7),
                components={"SPY": {"regime": sign, "surprise": -sign, "trend": 1.0}},
                forward_returns={"SPY": 0.01 * sign},
            )
        )
    return rows


def test_weights_selected_on_training_rows_only() -> None:
    grid = [
        ComponentWeights(regime=a, surprise=b, trend=0.0) for a, b in ((1, 0), (0, 1), (0.5, 0.5))
    ]
    rows = _rows(20)
    cutoff = rows[9].forward_end
    sel = select_weights(rows, grid, cutoff)
    assert sel.selected == ComponentWeights(regime=1, surprise=0, trend=0)
    assert sel.n_rows_used == 10 and len(sel.candidates) == 3
    flipped = rows[:10] + [
        r.model_copy(update={"forward_returns": {"SPY": -r.forward_returns["SPY"]}})
        for r in rows[10:]
    ]
    assert select_weights(flipped, grid, cutoff) == sel
    with pytest.raises(ValueError, match="no training"):
        select_weights(rows, grid, T)
    with pytest.raises(ValueError, match="at least one"):
        select_weights(rows, [], cutoff)
