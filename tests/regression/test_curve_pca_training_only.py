"""Training-only yield-curve PCA (Task 3.8)."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from macrosignal.data.treasury import CurveType, parse_treasury_csv
from macrosignal.features.curve_pca import CurvePCAError, fit_curve_pca

NY = ZoneInfo("America/New_York")
TENORS = ("3M", "2Y", "5Y", "10Y", "30Y")
COLUMNS = ("3 Mo", "2 Yr", "5 Yr", "10 Yr", "30 Yr")


def _synthetic_csv(
    start: date, days: int, shift: float = 0.0, drop: set[date] | None = None
) -> str:
    """Deterministic synthetic curves: level/slope/curvature driven by smooth signals."""
    lines = ["Date," + ",".join(COLUMNS)]
    d = start
    i = 0
    while i < days:
        if d.weekday() < 5:
            level = 3.5 + 0.5 * math.sin(i / 9) + shift
            slope = 0.8 * math.cos(i / 13)
            curv = 0.2 * math.sin(i / 5)
            mats = np.array([0.25, 2, 5, 10, 30])
            ys = (
                level
                + slope * (np.log(mats) / np.log(30))
                + curv * np.exp(-((np.log(mats) - 1.6) ** 2))
            )
            cells = [f"{y:.4f}" for y in ys]
            if drop and d in drop:
                cells[-1] = "N/A"
            lines.append(d.strftime("%m/%d/%Y") + "," + ",".join(cells))
            i += 1
        d += timedelta(days=1)
    return "\n".join(lines) + "\n"


def _batch(text: str):  # type: ignore[no-untyped-def]
    return parse_treasury_csv(
        text,
        CurveType.NOMINAL,
        snapshot_id="raw_synth",
        retrieved_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


PAST = _batch(_synthetic_csv(date(2026, 1, 5), 120, drop={date(2026, 2, 3)}))
FUTURE = _batch(_synthetic_csv(date(2026, 7, 1), 60, shift=2.0))  # regime shift later
CUTOFF = datetime(2026, 6, 1, 9, 0, tzinfo=NY)


def _fit(batches, **kw):  # type: ignore[no-untyped-def]
    args = {
        "curve": CurveType.NOMINAL,
        "tenors": TENORS,
        "train_cutoff": CUTOFF,
        "n_components": 3,
        "fit_id": "pca_fit_1",
    }
    args.update(kw)
    return fit_curve_pca(batches, **args)


def test_future_rows_cannot_change_frozen_fit() -> None:
    past_only = _fit([PAST])
    with_future = _fit([PAST, FUTURE])
    assert past_only.params_hash == with_future.params_hash
    assert past_only.train_end < CUTOFF.date()
    assert past_only.n_excluded_incomplete == 1


def test_historical_transform_is_stable_after_more_data() -> None:
    frozen = _fit([PAST])
    hist_day = date(2026, 3, 2)
    curve = PAST.curve_on(hist_day)
    before = frozen.transform(curve)
    refit_later_window = _fit([PAST, FUTURE])  # same cutoff
    assert refit_later_window.transform(curve) == before
    moved_cutoff = _fit(
        [PAST, FUTURE], train_cutoff=datetime(2026, 9, 30, tzinfo=NY), fit_id="pca_fit_2"
    )
    assert moved_cutoff.params_hash != frozen.params_hash  # only a new cutoff (new fit) differs
    assert frozen.transform(curve) == before


def test_signs_and_variance() -> None:
    f = _fit([PAST])
    assert sum(f.loadings[0]) > 0
    assert f.loadings[1][-1] > 0 and f.loadings[2][-1] >= 0
    ratios = f.explained_variance_ratio
    assert list(ratios) == sorted(ratios, reverse=True)
    assert sum(f.explained_variance_ratio) <= 1.0 + 1e-12
    level_now = f.transform(FUTURE.curve_on(date(2026, 7, 1)))[0]
    level_then = f.transform(PAST.curve_on(date(2026, 1, 5)))[0]
    assert level_now > level_then  # +2pp regime shift shows up in the frozen level factor


def test_errors() -> None:
    with pytest.raises(CurvePCAError, match="complete training rows"):
        _fit([PAST], train_cutoff=datetime(2026, 1, 6, tzinfo=NY))
    with pytest.raises(CurvePCAError, match="n_components"):
        _fit([PAST], n_components=6)
    with pytest.raises(CurvePCAError, match="timezone-aware"):
        _fit([PAST], train_cutoff=datetime(2026, 6, 1))
    with pytest.raises(CurvePCAError, match="does not impute"):
        _fit([PAST]).transform({"3M": 1.0})
    flat = _batch("Date,3 Mo,2 Yr\n01/05/2026,1.0,2.0\n01/06/2026,1.0,2.1\n")
    with pytest.raises(CurvePCAError, match="zero training variance"):
        _fit([flat], tenors=("3M", "2Y"), n_components=1)
