"""Ex-ante volatility and covariance estimation at rebalance time.

``estimate_covariance`` uses only research returns whose session ends strictly
before the rebalance session (``include_rebalance_session=False``, the default:
a decision taken before that session's close cannot know its return), over the
last ``lookback`` sessions, on complete-case rows across the assets that have
at least ``min_observations`` returns in the window (others are excluded with
a reason, never filled).

Methods:

* ``sample`` - sample covariance;
* ``ledoit_wolf`` - Ledoit-Wolf shrinkage towards a scaled identity (stable,
  well-conditioned baseline);
* ``ewma`` - exponentially weighted covariance with half-life ``halflife``.

Results are annualized with ``periods_per_year`` and stored with the estimation
window, number of observations, method and the rebalance (fit) timestamp.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Literal

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sklearn.covariance import LedoitWolf  # type: ignore[import-untyped]

from macrosignal.portfolio.returns import AssetReturnSeries


class CovarianceEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_time: AwareDatetime
    rebalance_session: date
    method: Literal["sample", "ledoit_wolf", "ewma"]
    assets: tuple[str, ...]
    excluded: dict[str, str]
    window_start: date
    window_end: date
    n_observations: int
    periods_per_year: int
    covariance: tuple[tuple[float, ...], ...]
    shrinkage: float | None = None

    @property
    def matrix(self) -> np.ndarray:
        return np.array(self.covariance)

    @property
    def volatilities(self) -> dict[str, float]:
        return {
            a: float(np.sqrt(v)) for a, v in zip(self.assets, np.diag(self.matrix), strict=True)
        }


class RiskEstimationError(ValueError):
    """Not enough history to estimate risk at the rebalance time."""


class RiskSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Literal["sample", "ledoit_wolf", "ewma"] = "ledoit_wolf"
    lookback: int = Field(default=252, ge=2)
    min_observations: int = Field(default=60, ge=2)
    halflife: float = Field(default=60.0, gt=0)
    periods_per_year: int = Field(default=252, ge=1)
    include_rebalance_session: bool = False


def estimate_covariance(
    returns: Mapping[str, AssetReturnSeries],
    rebalance_session: date,
    fit_time: datetime,
    settings: RiskSettings | None = None,
) -> CovarianceEstimate:
    s = settings or RiskSettings()
    if fit_time.tzinfo is None or fit_time.utcoffset() is None:
        raise RiskEstimationError("fit_time must be timezone-aware")
    usable: dict[str, dict[date, float]] = {}
    for asset, series in returns.items():
        usable[asset] = {
            d: r
            for d, r in series.as_dict().items()
            if d < rebalance_session or (s.include_rebalance_session and d == rebalance_session)
        }
    all_days = sorted({d for v in usable.values() for d in v})[-s.lookback :]
    excluded: dict[str, str] = {}
    assets: list[str] = []
    for asset in sorted(usable):
        n = sum(1 for d in all_days if d in usable[asset])
        if n < s.min_observations:
            excluded[asset] = f"only {n} returns in window (< {s.min_observations})"
        else:
            assets.append(asset)
    if not assets:
        raise RiskEstimationError("no asset has enough return history before the rebalance")
    rows = [d for d in all_days if all(d in usable[a] for a in assets)]
    if len(rows) < s.min_observations:
        raise RiskEstimationError(f"only {len(rows)} complete rows across {assets}")
    x = np.array([[usable[a][d] for a in assets] for d in rows])
    shrink = None
    if s.method == "sample":
        cov = np.atleast_2d(np.cov(x, rowvar=False, ddof=1))
    elif s.method == "ledoit_wolf":
        lw = LedoitWolf().fit(x)
        cov, shrink = lw.covariance_, float(lw.shrinkage_)
    else:
        n = len(x)
        w = 0.5 ** (np.arange(n)[::-1] / s.halflife)
        w /= w.sum()
        mu = w @ x
        dx = x - mu
        cov = (dx * w[:, None]).T @ dx / (1 - np.sum(w**2))
    cov = cov * s.periods_per_year
    return CovarianceEstimate(
        fit_time=fit_time,
        rebalance_session=rebalance_session,
        method=s.method,
        assets=tuple(assets),
        excluded=excluded,
        window_start=rows[0],
        window_end=rows[-1],
        n_observations=len(rows),
        periods_per_year=s.periods_per_year,
        covariance=tuple(tuple(map(float, r)) for r in cov),
        shrinkage=shrink,
    )
