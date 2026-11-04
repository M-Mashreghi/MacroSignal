"""Daily event-study return windows (Task 4.12)."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import AssetMetadata, MarketObservation, ReleaseEvent
from macrosignal.event_study.alignment import align_event
from macrosignal.event_study.daily_windows import DailyWindow, WindowStatus, daily_event_windows

NY = ZoneInfo("America/New_York")
CAL = UsTradingCalendar()
SESSIONS = CAL.sessions(date(2026, 10, 1), date(2026, 11, 30))
PRICES = {d: 100.0 + i for i, d in enumerate(SESSIONS)}
ASSET = AssetMetadata(
    asset_id="SPY",
    role="broad_us_equity",
    provider="SYNTHETIC",
    currency="USD",
    timezone="America/New_York",
    first_tradable_date=date(2026, 10, 1),
    coverage_start=date(2026, 10, 1),
    price_adjustment_policy="split_and_dividend_adjusted",
    return_convention="adjusted_close_to_adjusted_close",
)


def _prices(skip: set[date] | None = None) -> list[MarketObservation]:
    return [
        MarketObservation(
            asset_id="SPY",
            timestamp=CAL.session_close(d),
            field="adjusted_close",
            value=v,
            currency="USD",
            provider="SYNTHETIC",
            adjustment_policy="split_and_dividend_adjusted",
            retrieved_at=datetime(2026, 12, 31, tzinfo=UTC),
            snapshot_id="raw",
        )
        for d, v in PRICES.items()
        if not skip or d not in skip
    ]


def _windows(at: datetime, **kw):  # type: ignore[no-untyped-def]
    ev = ReleaseEvent(
        release_id="X-1",
        release_family="CPI",
        release_name="CPI",
        source="bls",
        calendar_snapshot_id="c",
        source_timezone="America/New_York",
        scheduled_at=at,
        actual_release_at=at,
        reference_start=date(2026, 9, 1),
        reference_end=date(2026, 9, 30),
        release_stage="initial",
    )
    w = daily_event_windows(align_event(ev, CAL), ASSET, _prices(**kw), CAL)
    return {x.window: x for x in w}


def _ret(a: date, b: date) -> float:
    return PRICES[b] / PRICES[a] - 1


def test_pre_open_release_windows() -> None:
    w = _windows(datetime(2026, 10, 15, 8, 30, tzinfo=NY))
    rd = w[DailyWindow.RELEASE_DAY]
    assert (rd.start_session, rd.end_session) == (date(2026, 10, 14), date(2026, 10, 15))
    assert rd.simple_return == pytest.approx(_ret(date(2026, 10, 14), date(2026, 10, 15)))
    assert rd.contains_reaction and rd.frequency == "daily"
    assert w[DailyWindow.NEXT_SESSION].status is WindowStatus.NOT_APPLICABLE
    assert w[DailyWindow.ONE_DAY].simple_return == rd.simple_return
    five = w[DailyWindow.FIVE_DAY]
    assert five.end_session == date(2026, 10, 21)
    assert five.log_return == pytest.approx(
        math.log(PRICES[date(2026, 10, 21)] / PRICES[date(2026, 10, 14)])
    )


def test_post_close_release_windows() -> None:
    w = _windows(datetime(2026, 10, 15, 16, 30, tzinfo=NY))
    rd = w[DailyWindow.RELEASE_DAY]
    assert rd.status is WindowStatus.OK and not rd.contains_reaction
    ns = w[DailyWindow.NEXT_SESSION]
    assert (ns.start_session, ns.end_session) == (date(2026, 10, 15), date(2026, 10, 16))
    assert w[DailyWindow.ONE_DAY].start_session == date(2026, 10, 15)


def test_market_hours_flags_pre_event_trading() -> None:
    w = _windows(datetime(2026, 10, 28, 14, 0, tzinfo=NY))
    assert w[DailyWindow.ONE_DAY].includes_pre_event_trading
    assert w[DailyWindow.RELEASE_DAY].includes_pre_event_trading


def test_holiday_weekend_and_missing_prices() -> None:
    w = _windows(datetime(2026, 10, 17, 10, 0, tzinfo=NY))  # Saturday
    assert w[DailyWindow.RELEASE_DAY].status is WindowStatus.NOT_APPLICABLE
    assert w[DailyWindow.NEXT_SESSION].start_session == date(2026, 10, 16)
    missing = _windows(datetime(2026, 10, 15, 8, 30, tzinfo=NY), skip={date(2026, 10, 15)})
    assert missing[DailyWindow.ONE_DAY].status is WindowStatus.MISSING_PRICE
    assert missing[DailyWindow.ONE_DAY].simple_return is None


def test_lifecycle_and_series_guards() -> None:
    w = _windows(datetime(2026, 10, 1, 8, 30, tzinfo=NY))  # baseline before first tradable date
    assert w[DailyWindow.ONE_DAY].status is WindowStatus.OUTSIDE_LIFECYCLE
    bad = _prices()[:2]
    bad[1] = bad[1].model_copy(update={"field": "close", "adjustment_policy": "unadjusted"})
    ev = ReleaseEvent(
        release_id="X-1",
        release_family="CPI",
        release_name="CPI",
        source="bls",
        calendar_snapshot_id="c",
        source_timezone="America/New_York",
        scheduled_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        actual_release_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        reference_start=date(2026, 9, 1),
        reference_end=date(2026, 9, 30),
    )
    with pytest.raises(ValueError, match="one asset / field"):
        daily_event_windows(align_event(ev, CAL), ASSET, bad, CAL)
