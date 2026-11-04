"""Trend guardrail signal (Task 5.7)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.config import load_config_file
from macrosignal.config.models import SignalConfig
from macrosignal.domain import ResearchReturnSpec
from macrosignal.portfolio.returns import AssetReturnSeries, SessionReturn
from macrosignal.signals.trend import TrendSettings, TrendStatus, trend_signals

ROOT = Path(__file__).resolve().parents[2]
CAL = UsTradingCalendar()
SPEC = ResearchReturnSpec(
    convention="adjusted_close_to_adjusted_close",
    price_field="adjusted_close",
    adjustment_policy="split_and_dividend_adjusted",
)
SESSIONS = CAL.sessions(date(2026, 1, 2), date(2026, 6, 30))
CFG = load_config_file(ROOT / "configs/signals/signals_v1.yaml", SignalConfig).trend_component


def _series(asset: str, r: float, shock_on: date | None = None) -> AssetReturnSeries:
    rets = tuple(
        SessionReturn(session=b, previous_session=a, simple_return=(-0.5 if b == shock_on else r))
        for a, b in zip(SESSIONS, SESSIONS[1:], strict=False)
    )
    return AssetReturnSeries(
        asset_id=asset,
        spec=SPEC,
        returns=rets,
        missing_sessions=(),
        suspicious_moves=(),
        max_abs_return=0.9,
    )


def test_direction_from_past_window() -> None:
    s = TrendSettings.from_config(CFG)
    assert s.lookback_days == 60 and s.enabled
    out = trend_signals(
        {"SPY": _series("SPY", 0.001), "TLT": _series("TLT", -0.001)}, date(2026, 5, 1), s
    )
    assert out["SPY"].direction == 1 and out["TLT"].direction == -1
    assert out["SPY"].window_end == date(2026, 4, 30) and out["SPY"].window_start >= date(
        2026, 3, 2
    )
    assert out["SPY"].trailing_return == pytest.approx(1.001 ** out["SPY"].n_returns - 1)


def test_decision_session_return_not_used() -> None:
    s = TrendSettings.from_config(CFG)
    shocked = {"SPY": _series("SPY", 0.001, shock_on=date(2026, 5, 1))}
    assert trend_signals(shocked, date(2026, 5, 1), s)["SPY"].direction == 1
    assert trend_signals(shocked, date(2026, 5, 4), s)["SPY"].direction == -1


def test_missing_and_disabled() -> None:
    s = TrendSettings.from_config(CFG)
    early = trend_signals({"SPY": _series("SPY", 0.001)}, date(2026, 1, 20), s)
    assert early["SPY"].status is TrendStatus.MISSING and early["SPY"].direction is None
    off = TrendSettings(enabled=False, lookback_days=60)
    assert (
        trend_signals({"SPY": _series("SPY", 0.001)}, date(2026, 5, 1), off)["SPY"].status
        is TrendStatus.DISABLED
    )
