"""Intraday event-study interface (Task 4.13)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from macrosignal.domain import MarketObservation
from macrosignal.event_study.intraday import (
    IntradayBar,
    IntradayBarSeries,
    IntradayDataError,
    IntradayWindowSpec,
    UnconfiguredIntradayProvider,
    intraday_event_return,
)

NY = ZoneInfo("America/New_York")
EVENT = datetime(2026, 10, 15, 8, 30, tzinfo=NY)


def _series(freq_min: int = 5, convention: str = "bar_end") -> IntradayBarSeries:
    start = datetime(2026, 10, 15, 8, 0, tzinfo=NY)
    bars = tuple(
        IntradayBar(
            timestamp=start + timedelta(minutes=freq_min * i), open=100 + i, close=100.5 + i
        )
        for i in range(20)
    )
    return IntradayBarSeries(
        asset_id="SPY",
        provider="synthetic",
        frequency=timedelta(minutes=freq_min),
        timestamp_convention=convention,
        timezone="America/New_York",
        bars=bars,
    )


def test_window_return_from_bar_ends() -> None:
    r = intraday_event_return(
        EVENT, _series(), IntradayWindowSpec(minutes_before=5, minutes_after=25)
    )
    assert r.start_bar_end == datetime(2026, 10, 15, 8, 25, tzinfo=NY)
    assert r.end_bar_end == datetime(2026, 10, 15, 8, 55, tzinfo=NY)
    assert r.simple_return == pytest.approx((100.5 + 11) / (100.5 + 5) - 1)
    start_conv = intraday_event_return(
        EVENT,
        _series(convention="bar_start"),
        IntradayWindowSpec(minutes_before=5, minutes_after=25),
    )
    assert start_conv.start_bar_end == datetime(2026, 10, 15, 8, 25, tzinfo=NY)


def test_daily_data_rejected() -> None:
    with pytest.raises(ValidationError, match="not intraday"):
        IntradayBarSeries(
            asset_id="SPY",
            provider="p",
            frequency=timedelta(days=1),
            timestamp_convention="bar_end",
            timezone="America/New_York",
            bars=_series().bars,
        )
    daily_bars = tuple(
        IntradayBar(timestamp=datetime(2026, 10, d, 16, 0, tzinfo=NY), open=1, close=1)
        for d in (13, 14, 15)
    )
    with pytest.raises(ValidationError, match="daily sampling"):
        IntradayBarSeries(
            asset_id="SPY",
            provider="p",
            frequency=timedelta(minutes=30),
            timestamp_convention="bar_end",
            timezone="America/New_York",
            bars=daily_bars,
        )
    obs = [
        MarketObservation(
            asset_id="SPY",
            timestamp=datetime(2026, 10, 15, 16, tzinfo=NY),
            field="close",
            value=1.0,
            currency="USD",
            provider="p",
            adjustment_policy="unadjusted",
            retrieved_at=datetime(2026, 11, 1, tzinfo=UTC),
            snapshot_id="s",
        )
    ]
    with pytest.raises(IntradayDataError, match="daily observations"):
        intraday_event_return(EVENT, obs, IntradayWindowSpec(minutes_before=0, minutes_after=30))


def test_coverage_and_spec_guards() -> None:
    with pytest.raises(IntradayDataError, match="do not cover"):
        intraday_event_return(
            EVENT, _series(), IntradayWindowSpec(minutes_before=60, minutes_after=30)
        )
    with pytest.raises(IntradayDataError, match="shorter than the bar frequency"):
        intraday_event_return(
            EVENT, _series(freq_min=30), IntradayWindowSpec(minutes_before=0, minutes_after=1)
        )
    with pytest.raises(IntradayDataError, match="timezone-aware"):
        intraday_event_return(
            datetime(2026, 10, 15, 8, 30),
            _series(),
            IntradayWindowSpec(minutes_before=5, minutes_after=5),
        )


def test_v1_provider_is_unconfigured() -> None:
    with pytest.raises(NotImplementedError):
        UnconfiguredIntradayProvider().fetch_bars("SPY", EVENT, EVENT, timedelta(minutes=5))
    assert date(2026, 10, 15) == EVENT.date()
