"""Daily event-study return windows (close-to-close, no intraday claims).

Given an :class:`EventMarketAlignment` and one asset's daily price series (one
field and adjustment policy, e.g. ``adjusted_close``), returns are computed
from session-close prices only:

==============  ======================================================  =================
window          start close -> end close                                contains reaction
==============  ======================================================  =================
release_day     session before the event date -> event-date session     only if pre-open /
                (only when the event date is a session)                 market-hours
next_session    event-date session (or last before) -> next session     post-close /
                                                                         non-session only
1d              baseline -> first reacting session                      always
5d              baseline -> 5th session counting the reacting one       always
==============  ======================================================  =================

Each window declares frequency ``daily`` and the price convention; prices must
exist exactly at the declared session closes (a missing close makes the window
``missing_price``, never filled), and windows starting before the asset's first
tradable date are ``outside_lifecycle``.  Daily windows never claim intraday
timing: for market-hours events ``1d`` contains pre-event trading of that day,
which is recorded in ``includes_pre_event_trading``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import AdjustmentPolicy, AssetMetadata, MarketObservation, PriceField
from macrosignal.event_study.alignment import EventMarketAlignment, EventTiming


class DailyWindow(StrEnum):
    RELEASE_DAY = "release_day"
    NEXT_SESSION = "next_session"
    ONE_DAY = "1d"
    FIVE_DAY = "5d"


class WindowStatus(StrEnum):
    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    MISSING_PRICE = "missing_price"
    OUTSIDE_LIFECYCLE = "outside_lifecycle"


class EventWindowReturn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    asset_id: str
    window: DailyWindow
    frequency: str = "daily"
    price_field: PriceField
    adjustment_policy: AdjustmentPolicy
    status: WindowStatus
    start_session: date | None = None
    end_session: date | None = None
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None
    start_price: float | None = None
    end_price: float | None = None
    simple_return: float | None = None
    log_return: float | None = None
    contains_reaction: bool = False
    includes_pre_event_trading: bool = False


def _price_index(prices: Sequence[MarketObservation]) -> dict[AwareDatetime, MarketObservation]:
    fields = {(p.asset_id, p.field, p.adjustment_policy) for p in prices}
    if len(fields) > 1:
        raise ValueError(
            f"one asset / field / adjustment per series, got {sorted(map(str, fields))}"
        )
    index: dict[AwareDatetime, MarketObservation] = {}
    for p in prices:
        if p.timestamp in index:
            raise ValueError(f"duplicate price at {p.timestamp.isoformat()}")
        index[p.timestamp] = p
    return index


def daily_event_windows(
    alignment: EventMarketAlignment,
    asset: AssetMetadata,
    prices: Sequence[MarketObservation],
    calendar: UsTradingCalendar,
) -> list[EventWindowReturn]:
    if not prices:
        raise ValueError("no prices supplied")
    index = _price_index(prices)
    sample = prices[0]
    if sample.asset_id != asset.asset_id:
        raise ValueError("prices do not belong to the asset")
    if sample.field in (PriceField.OPEN, PriceField.HIGH, PriceField.LOW, PriceField.VOLUME):
        raise ValueError("daily event windows use close-type prices")

    a = alignment
    event_day = a.event_time_local.date()
    pre_or_intraday = a.timing in (EventTiming.PRE_OPEN, EventTiming.MARKET_HOURS)

    def build(
        window: DailyWindow,
        start: date | None,
        end: date | None,
        contains: bool,
        pre_event: bool = False,
    ) -> EventWindowReturn:
        base: dict[str, Any] = {
            "release_id": a.release_id,
            "asset_id": asset.asset_id,
            "window": window,
            "price_field": sample.field,
            "adjustment_policy": sample.adjustment_policy,
        }
        if start is None or end is None:
            return EventWindowReturn(**base, status=WindowStatus.NOT_APPLICABLE)
        st, et = calendar.session_close(start), calendar.session_close(end)
        common: dict[str, Any] = {
            **base,
            "start_session": start,
            "end_session": end,
            "start_time": st,
            "end_time": et,
            "contains_reaction": contains,
            "includes_pre_event_trading": pre_event,
        }
        if not asset.is_covered_on(start) or not asset.is_covered_on(end):
            return EventWindowReturn(**common, status=WindowStatus.OUTSIDE_LIFECYCLE)
        p0, p1 = index.get(st), index.get(et)
        if p0 is None or p1 is None:
            return EventWindowReturn(**common, status=WindowStatus.MISSING_PRICE)
        return EventWindowReturn(
            **common,
            status=WindowStatus.OK,
            start_price=p0.value,
            end_price=p1.value,
            simple_return=p1.value / p0.value - 1.0,
            log_return=math.log(p1.value / p0.value),
        )

    out: list[EventWindowReturn] = []
    if a.timing is not EventTiming.DATE_LEVEL and calendar.is_session(event_day):
        out.append(
            build(
                DailyWindow.RELEASE_DAY,
                calendar.previous_session(event_day),
                event_day,
                contains=pre_or_intraday,
                pre_event=a.timing is EventTiming.MARKET_HOURS,
            )
        )
    else:
        out.append(build(DailyWindow.RELEASE_DAY, None, None, False))
    if pre_or_intraday:
        out.append(build(DailyWindow.NEXT_SESSION, None, None, False))
    else:
        start = (
            event_day if calendar.is_session(event_day) else calendar.previous_session(event_day)
        )
        out.append(build(DailyWindow.NEXT_SESSION, start, calendar.next_session(event_day), True))
    out.append(
        build(
            DailyWindow.ONE_DAY,
            a.baseline_session,
            a.reaction_session,
            True,
            pre_event=a.timing is EventTiming.MARKET_HOURS,
        )
    )
    end5 = a.reaction_session
    for _ in range(4):
        end5 = calendar.next_session(end5)
    out.append(
        build(
            DailyWindow.FIVE_DAY,
            a.baseline_session,
            end5,
            True,
            pre_event=a.timing is EventTiming.MARKET_HOURS,
        )
    )
    return out
