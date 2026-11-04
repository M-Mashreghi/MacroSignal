"""Cash / risk-free return engine (Task 5.3)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.data.treasury import CurveType, parse_treasury_csv
from macrosignal.domain import CashReturnSpec, RiskFreeSpec
from macrosignal.portfolio.cash import RatePoint, cash_returns, rates_from_curve, risk_free_returns

NY = ZoneInfo("America/New_York")
CAL = UsTradingCalendar()


def _rate(d: date, pct: float) -> RatePoint:
    return RatePoint(
        observation_date=d,
        annual_rate_pct=pct,
        available_at=datetime.combine(d, time(23, 59, 59), tzinfo=NY),
        source_id="DTB3",
    )


RATES = [_rate(date(2026, 11, 2), 4.0), _rate(date(2026, 11, 5), 3.6)]


def test_zero_cash_is_explicit_zero() -> None:
    s = cash_returns(CashReturnSpec(mode="zero"), CAL, date(2026, 11, 2), date(2026, 11, 9))
    assert s.mode == "zero" and all(v == 0.0 for v in s.as_dict().values())
    assert len(s.periods) == 5


def test_proxy_uses_rate_known_at_period_start() -> None:
    s = cash_returns(
        CashReturnSpec(mode="proxy", proxy_series_id="DTB3"),
        CAL,
        date(2026, 11, 2),
        date(2026, 11, 9),
        RATES,
    )
    by = {p.session: p for p in s.periods}
    # Period 11/2 close -> 11/3 close: the 11/2 rate is only known at 11/2 23:59:59 -> missing.
    assert by[date(2026, 11, 3)].cash_return is None
    assert by[date(2026, 11, 4)].annual_rate_pct == 4.0
    assert by[date(2026, 11, 4)].cash_return == pytest.approx(0.04 / 360)
    # The 11/5 rate applies from the period starting 11/6 close, not 11/5 close.
    assert by[date(2026, 11, 6)].annual_rate_pct == 4.0
    assert by[date(2026, 11, 9)].annual_rate_pct == 3.6
    assert by[date(2026, 11, 9)].days == 3
    assert by[date(2026, 11, 9)].cash_return == pytest.approx(0.036 * 3 / 360)
    assert s.missing_sessions == (date(2026, 11, 3),)
    assert s.day_count == "act_360_simple"


def test_risk_free_spec_and_curve_rates() -> None:
    nominal = parse_treasury_csv(
        (Path(__file__).resolve().parents[1] / "fixtures/treasury/nominal.csv").read_text("utf-8"),
        CurveType.NOMINAL,
        snapshot_id="raw",
        retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
    )
    rates = rates_from_curve(list(nominal.points))
    assert {r.source_id for r in rates} == {"nominal_3M"}
    rf = risk_free_returns(
        RiskFreeSpec(mode="treasury_bill_proxy", series_id="nominal_3M"),
        CAL,
        date(2026, 10, 15),
        date(2026, 10, 19),
        rates,
    )
    # Period starts at the 10/16 close: the 10/16 curve is only known at end of day, so the
    # 10/15 3M yield (3.96) applies.
    assert rf.as_dict()[date(2026, 10, 19)] == pytest.approx(3.96 / 100 * 3 / 360)
    zero = risk_free_returns(RiskFreeSpec(mode="zero"), CAL, date(2026, 10, 15), date(2026, 10, 19))
    assert set(zero.as_dict().values()) == {0.0}


def test_guards() -> None:
    with pytest.raises(ValueError, match="needs rate observations"):
        cash_returns(
            CashReturnSpec(mode="proxy", proxy_series_id="DTB3"),
            CAL,
            date(2026, 11, 2),
            date(2026, 11, 9),
        )
    with pytest.raises(ValueError, match="must all come from"):
        cash_returns(
            CashReturnSpec(mode="proxy", proxy_series_id="OTHER"),
            CAL,
            date(2026, 11, 2),
            date(2026, 11, 9),
            RATES,
        )
