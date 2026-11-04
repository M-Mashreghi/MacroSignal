"""Optional trend / momentum guardrail from past prices only.

For a decision on session ``d`` the guardrail uses research returns of sessions
strictly before ``d`` whose session date lies within the last
``lookback_days`` calendar days (``trend_component.lookback_days`` in the
signal config), i.e. information ending at the previous session's close:

``trend_a = +1`` if the compounded return over that window is positive,
``-1`` if negative, ``0`` if exactly flat.  With fewer than
``min_observations`` returns the asset's trend is *missing* (no guardrail, not
an inferred direction).  When the component is disabled every asset is
reported as ``disabled`` so it can be ablated cleanly.  Each result records the
window bounds and the number of returns used.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from macrosignal.config.models import TrendComponentSpec
from macrosignal.portfolio.returns import AssetReturnSeries


class TrendStatus(StrEnum):
    OK = "ok"
    MISSING = "missing"
    DISABLED = "disabled"


class TrendSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    decision_session: date
    status: TrendStatus
    direction: int | None = None
    trailing_return: float | None = None
    window_start: date | None = None
    window_end: date | None = None
    n_returns: int = 0
    lookback_days: int


class TrendSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool
    lookback_days: int = Field(gt=0)
    min_observations: int = Field(default=20, ge=1)

    @classmethod
    def from_config(cls, spec: TrendComponentSpec, min_observations: int = 20) -> TrendSettings:
        return cls(
            enabled=spec.enabled,
            lookback_days=spec.lookback_days,
            min_observations=min_observations,
        )


def trend_signals(
    returns: Mapping[str, AssetReturnSeries], decision_session: date, settings: TrendSettings
) -> dict[str, TrendSignal]:
    out: dict[str, TrendSignal] = {}
    start = decision_session - timedelta(days=settings.lookback_days)
    for asset, series in returns.items():
        base: dict[str, Any] = {
            "asset_id": asset,
            "decision_session": decision_session,
            "lookback_days": settings.lookback_days,
        }
        if not settings.enabled:
            out[asset] = TrendSignal(**base, status=TrendStatus.DISABLED)
            continue
        window = sorted(
            (r for r in series.returns if start <= r.session < decision_session),
            key=lambda r: r.session,
        )
        if len(window) < settings.min_observations:
            out[asset] = TrendSignal(**base, status=TrendStatus.MISSING, n_returns=len(window))
            continue
        growth = 1.0
        for r in window:
            growth *= 1.0 + r.simple_return
        trailing = growth - 1.0
        direction = 1 if trailing > 0 else (-1 if trailing < 0 else 0)
        out[asset] = TrendSignal(
            **base,
            status=TrendStatus.OK,
            direction=direction,
            trailing_return=trailing,
            window_start=window[0].session,
            window_end=window[-1].session,
            n_returns=len(window),
        )
    return out
