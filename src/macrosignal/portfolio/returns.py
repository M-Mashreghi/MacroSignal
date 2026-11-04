"""Research return engine with corporate-action semantics.

Computes session-to-session research returns for one asset from its daily
price observations under a :class:`~macrosignal.domain.ResearchReturnSpec`
(Task 1.8), separately from any execution-price simulation:

* the observations must use exactly the spec's price field and adjustment
  policy, and the asset's declared return convention must match the spec;
* prices are taken at session closes of the explicit trading calendar; a
  session without a price makes the returns into *and* out of it missing -
  gaps are reported (``missing_sessions``), never bridged or filled;
* only sessions inside the asset's tradable lifecycle and coverage count;
* one-session moves larger than ``max_abs_return`` are flagged as suspected
  unadjusted corporate actions (``suspicious_moves``) and, with
  ``reject_suspicious=True``, abort the calculation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import AssetMetadata, MarketObservation, ResearchReturnSpec


class ReturnSemanticsError(ValueError):
    """Price data are inconsistent with the declared return convention."""


class SessionReturn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session: date
    previous_session: date
    simple_return: float


class AssetReturnSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    spec: ResearchReturnSpec
    returns: tuple[SessionReturn, ...]
    missing_sessions: tuple[date, ...]
    suspicious_moves: tuple[date, ...]
    max_abs_return: float = Field(gt=0)

    def as_dict(self) -> dict[date, float]:
        return {r.session: r.simple_return for r in self.returns}


def compute_returns(
    asset: AssetMetadata,
    prices: Sequence[MarketObservation],
    spec: ResearchReturnSpec,
    calendar: UsTradingCalendar,
    start: date,
    end: date,
    *,
    max_abs_return: float = 0.35,
    reject_suspicious: bool = False,
) -> AssetReturnSeries:
    if asset.return_convention != spec.convention:
        raise ReturnSemanticsError(
            f"{asset.asset_id} declares {asset.return_convention.value}, run uses "
            f"{spec.convention.value}"
        )
    by_day: dict[date, float] = {}
    for p in prices:
        if p.asset_id != asset.asset_id:
            raise ReturnSemanticsError(f"price for {p.asset_id} passed for {asset.asset_id}")
        if (p.field, p.adjustment_policy) != (spec.price_field, spec.adjustment_policy):
            raise ReturnSemanticsError(
                f"{asset.asset_id}: {p.field.value}/{p.adjustment_policy.value} does not match "
                f"{spec.price_field.value}/{spec.adjustment_policy.value}"
            )
        day = asset.local_date(p.timestamp)
        if not calendar.is_session(day) or p.timestamp != calendar.session_close(day):
            raise ReturnSemanticsError(
                f"{asset.asset_id}: price at {p.timestamp} is not a session close"
            )
        if day in by_day:
            raise ReturnSemanticsError(f"{asset.asset_id}: duplicate price for {day}")
        by_day[day] = p.value

    sessions = [d for d in calendar.sessions(start, end) if asset.is_covered_on(d)]
    missing = tuple(d for d in sessions if d not in by_day)
    out: list[SessionReturn] = []
    suspicious: list[date] = []
    for prev, cur in zip(sessions, sessions[1:], strict=False):
        if prev not in by_day or cur not in by_day:
            continue
        r = by_day[cur] / by_day[prev] - 1.0
        if abs(r) > max_abs_return:
            suspicious.append(cur)
            if reject_suspicious:
                raise ReturnSemanticsError(
                    f"{asset.asset_id}: {r:.1%} move on {cur} looks like an unadjusted "
                    "corporate action"
                )
        out.append(SessionReturn(session=cur, previous_session=prev, simple_return=r))
    return AssetReturnSeries(
        asset_id=asset.asset_id,
        spec=spec,
        returns=tuple(out),
        missing_sessions=missing,
        suspicious_moves=tuple(suspicious),
        max_abs_return=max_abs_return,
    )
