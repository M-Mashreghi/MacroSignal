"""Cash / risk-free return engine with point-in-time rate alignment.

Uninvested capital earns an explicit return (``docs/RETURN_AND_EXECUTION_CONTRACT.md``):

* ``zero`` - exactly 0 every session;
* ``proxy`` - a short-rate series (annualized percent, e.g. a 3-month Treasury
  bill yield) accrued as simple interest, ACT/360, over each holding period
  ``previous session close -> session close``.

Point-in-time rule: the rate applied to a holding period is the latest rate
observation whose ``available_at`` is at or before the **start** of the period
(the previous session close).  If none exists the period's cash return is
*missing* - it is never silently set to zero.  Every period records the rate,
its observation date and availability, so Sharpe / flat-capital assumptions are
auditable.  The same engine serves the :class:`~macrosignal.domain.RiskFreeSpec`
used by performance metrics.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.data.treasury import YieldCurvePoint
from macrosignal.domain import (
    CashReturnMode,
    CashReturnSpec,
    MacroObservation,
    RiskFreeMode,
    RiskFreeSpec,
)

DAY_COUNT = "act_360_simple"


class RatePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_date: date
    annual_rate_pct: float
    available_at: AwareDatetime
    source_id: str


def rates_from_macro(observations: Sequence[MacroObservation]) -> list[RatePoint]:
    return [
        RatePoint(
            observation_date=o.reference_end,
            annual_rate_pct=o.value,
            available_at=o.availability.available_at,
            source_id=o.series_id,
        )
        for o in observations
    ]


def rates_from_curve(points: Sequence[YieldCurvePoint], tenor: str = "3M") -> list[RatePoint]:
    return [
        RatePoint(
            observation_date=p.observation_date,
            annual_rate_pct=p.yield_pct,
            available_at=p.availability.available_at,
            source_id=f"{p.curve.value}_{tenor}",
        )
        for p in points
        if p.tenor == tenor
    ]


class CashPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session: date
    previous_session: date
    cash_return: float | None
    annual_rate_pct: float | None
    rate_observation_date: date | None
    rate_available_at: AwareDatetime | None
    days: int


class CashReturnSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: str
    proxy_series_id: str | None
    day_count: str
    periods: tuple[CashPeriod, ...]

    @property
    def missing_sessions(self) -> tuple[date, ...]:
        return tuple(p.session for p in self.periods if p.cash_return is None)

    def as_dict(self) -> dict[date, float | None]:
        return {p.session: p.cash_return for p in self.periods}


def _engine(
    zero: bool,
    series_id: str | None,
    rates: Sequence[RatePoint],
    calendar: UsTradingCalendar,
    start: date,
    end: date,
) -> CashReturnSeries:
    sessions = calendar.sessions(start, end)
    ordered = sorted(rates, key=lambda r: r.available_at)
    if series_id is not None and any(r.source_id != series_id for r in ordered):
        raise ValueError(f"rate points must all come from {series_id}")
    keys = [r.available_at for r in ordered]
    periods: list[CashPeriod] = []
    for prev, cur in zip(sessions, sessions[1:], strict=False):
        days = (cur - prev).days
        if zero:
            periods.append(
                CashPeriod(
                    session=cur,
                    previous_session=prev,
                    cash_return=0.0,
                    annual_rate_pct=0.0,
                    rate_observation_date=None,
                    rate_available_at=None,
                    days=days,
                )
            )
            continue
        start_time = calendar.session_close(prev)
        idx = bisect_right(keys, start_time) - 1
        if idx < 0:
            periods.append(
                CashPeriod(
                    session=cur,
                    previous_session=prev,
                    cash_return=None,
                    annual_rate_pct=None,
                    rate_observation_date=None,
                    rate_available_at=None,
                    days=days,
                )
            )
            continue
        r = ordered[idx]
        periods.append(
            CashPeriod(
                session=cur,
                previous_session=prev,
                cash_return=r.annual_rate_pct / 100 * days / 360,
                annual_rate_pct=r.annual_rate_pct,
                rate_observation_date=r.observation_date,
                rate_available_at=r.available_at,
                days=days,
            )
        )
    return CashReturnSeries(
        mode="zero" if zero else "proxy",
        proxy_series_id=series_id,
        day_count=DAY_COUNT,
        periods=tuple(periods),
    )


def cash_returns(
    spec: CashReturnSpec,
    calendar: UsTradingCalendar,
    start: date,
    end: date,
    rates: Sequence[RatePoint] = (),
) -> CashReturnSeries:
    if spec.mode is CashReturnMode.ZERO:
        return _engine(True, None, (), calendar, start, end)
    if not rates:
        raise ValueError(f"cash proxy {spec.proxy_series_id} needs rate observations")
    return _engine(False, spec.proxy_series_id, rates, calendar, start, end)


def risk_free_returns(
    spec: RiskFreeSpec,
    calendar: UsTradingCalendar,
    start: date,
    end: date,
    rates: Sequence[RatePoint] = (),
) -> CashReturnSeries:
    if spec.mode is RiskFreeMode.ZERO:
        return _engine(True, None, (), calendar, start, end)
    if not rates:
        raise ValueError(f"risk-free series {spec.series_id} needs rate observations")
    return _engine(False, spec.series_id, rates, calendar, start, end)
