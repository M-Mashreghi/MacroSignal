"""Intraday event-study interface (contract only; optional in v1).

Defines what a future intraday provider must deliver before any intraday
reaction (e.g. a 30-minute window around 08:30) may be estimated:

* :class:`IntradayBarSeries` - one asset/provider, a fixed bar frequency
  strictly shorter than one day, an explicit timestamp convention
  (``bar_end`` or ``bar_start``), timezone-aware strictly increasing bars;
* :class:`IntradayProvider` - ``fetch_bars(asset_id, start, end, frequency)``;
* :class:`IntradayWindowSpec` - minutes before / after the event;
* :func:`intraday_event_return` - return from the last bar ending at or before
  ``event - before`` to the first bar ending at or after ``event + after``.

Daily data are rejected: a series whose frequency is one day or longer, daily
:class:`~macrosignal.domain.MarketObservation` lists, or bars whose spacing
reveals daily sampling.  :class:`UnconfiguredIntradayProvider` is the v1
default and refuses to produce data.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from macrosignal.domain import MarketObservation

MAX_INTRADAY_FREQUENCY = timedelta(hours=6)


class IntradayDataError(ValueError):
    """Data do not satisfy the intraday contract (e.g. daily data)."""


class IntradayBar(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: AwareDatetime
    open: FiniteFloat = Field(gt=0)
    close: FiniteFloat = Field(gt=0)


class IntradayBarSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    provider: str
    frequency: timedelta
    timestamp_convention: Literal["bar_end", "bar_start"]
    timezone: str
    bars: tuple[IntradayBar, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _check(self) -> IntradayBarSeries:
        if self.frequency <= timedelta(0) or self.frequency > MAX_INTRADAY_FREQUENCY:
            raise ValueError(
                f"frequency {self.frequency} is not intraday; "
                "daily data cannot feed intraday windows"
            )
        times = [b.timestamp for b in self.bars]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("bar timestamps must be strictly increasing")
        gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
        if min(gaps) >= timedelta(hours=20):
            raise ValueError("bar spacing reveals daily sampling; not intraday data")
        return self

    def bar_end(self, bar: IntradayBar) -> datetime:
        return (
            bar.timestamp
            if self.timestamp_convention == "bar_end"
            else bar.timestamp + self.frequency
        )


class IntradayProvider(Protocol):
    name: str

    def fetch_bars(
        self, asset_id: str, start: datetime, end: datetime, frequency: timedelta
    ) -> IntradayBarSeries: ...


class UnconfiguredIntradayProvider:
    """v1 default: intraday data are optional and not configured."""

    name = "unconfigured"

    def fetch_bars(
        self, asset_id: str, start: datetime, end: datetime, frequency: timedelta
    ) -> IntradayBarSeries:
        raise NotImplementedError("no intraday provider is configured in v1")


class IntradayWindowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    minutes_before: int = Field(ge=0)
    minutes_after: int = Field(gt=0)


class IntradayEventReturn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    event_time: AwareDatetime
    spec: IntradayWindowSpec
    frequency: timedelta
    start_bar_end: AwareDatetime
    end_bar_end: AwareDatetime
    start_price: float
    end_price: float
    simple_return: float


def intraday_event_return(
    event_time: datetime,
    series: IntradayBarSeries | Sequence[MarketObservation],
    spec: IntradayWindowSpec,
) -> IntradayEventReturn:
    if not isinstance(series, IntradayBarSeries):
        raise IntradayDataError(
            "intraday windows need an IntradayBarSeries; daily observations "
            "cannot be used for intraday reactions"
        )
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise IntradayDataError("event time must be timezone-aware")
    start_target = event_time - timedelta(minutes=spec.minutes_before)
    end_target = event_time + timedelta(minutes=spec.minutes_after)
    before = [b for b in series.bars if series.bar_end(b) <= start_target]
    after = [b for b in series.bars if series.bar_end(b) >= end_target]
    if not before or not after:
        raise IntradayDataError("bars do not cover the requested window")
    b0, b1 = before[-1], after[0]
    if end_target - start_target < series.frequency:
        raise IntradayDataError("window shorter than the bar frequency")
    return IntradayEventReturn(
        asset_id=series.asset_id,
        event_time=event_time,
        spec=spec,
        frequency=series.frequency,
        start_bar_end=series.bar_end(b0),
        end_bar_end=series.bar_end(b1),
        start_price=b0.close,
        end_price=b1.close,
        simple_return=b1.close / b0.close - 1.0,
    )
