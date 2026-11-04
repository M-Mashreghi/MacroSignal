"""Yield-curve shape features (Task 3.7)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from macrosignal.data.treasury import CurveType, parse_treasury_csv
from macrosignal.features.curve_shape import build_curve_shape_features

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "treasury"
NY = ZoneInfo("America/New_York")
RET = datetime(2026, 10, 20, tzinfo=UTC)


def _batch(name: str, curve: CurveType, text: str | None = None):  # type: ignore[no-untyped-def]
    body = text if text is not None else (FIX / name).read_text("utf-8")
    return parse_treasury_csv(body, curve, snapshot_id=f"raw_{curve.value}", retrieved_at=RET)


NOM = _batch("nominal.csv", CurveType.NOMINAL)
REAL = _batch("real.csv", CurveType.REAL)


def test_shape_arithmetic_from_latest_known_curve() -> None:
    fs = build_curve_shape_features([NOM, REAL], datetime(2026, 10, 17, 9, 0, tzinfo=NY))
    # 2026-10-16 curve: 3M 3.95, 2Y 3.60, 5Y 3.70, 10Y 4.00, 30Y 4.40; real 10Y 1.60
    assert fs.value("nominal_level_10y") == pytest.approx(4.00)
    assert fs.value("nominal_spread_10y_2y") == pytest.approx(0.40)
    assert fs.value("nominal_spread_10y_3m") == pytest.approx(0.05)
    assert fs.value("nominal_slope_30y_5y") == pytest.approx(0.70)
    assert fs.value("nominal_curvature") == pytest.approx(2 * 3.70 - 3.60 - 4.00)
    assert fs.value("breakeven_10y") == pytest.approx(2.40)
    f = fs.features["breakeven_10y"]
    assert f.observation_date == date(2026, 10, 16)
    assert f.input_snapshot_ids == ("raw_nominal", "raw_real")
    assert f.availability_precision.value == "inferred_eod"
    assert f.available_at == datetime(2026, 10, 16, 23, 59, 59, tzinfo=NY)
    assert fs.missing == {}


def test_missing_maturity_is_missing_not_interpolated() -> None:
    # On the 10/15 curve the nominal 30Y is N/A.
    fs = build_curve_shape_features([NOM, REAL], datetime(2026, 10, 16, 12, 0, tzinfo=NY))
    assert "nominal_slope_30y_5y" not in fs.features
    assert fs.missing["nominal_slope_30y_5y"] == "missing maturities: nominal 30Y"
    assert fs.value("nominal_spread_10y_2y") == pytest.approx(4.02 - 3.62)


def test_cross_curve_date_mismatch_rejected() -> None:
    real_late = _batch("real.csv", CurveType.REAL, "Date,10 YR\n10/15/2026,1.62\n")
    fs = build_curve_shape_features([NOM, real_late], datetime(2026, 10, 17, 9, 0, tzinfo=NY))
    assert "different dates" in fs.missing["breakeven_10y"]
    assert fs.value("real_level_10y") == 1.62


def test_same_day_curve_never_used_before_end_of_day() -> None:
    fs = build_curve_shape_features([NOM], datetime(2026, 10, 16, 15, 59, tzinfo=NY))
    assert all(f.observation_date == date(2026, 10, 15) for f in fs.features.values())
    assert "real_level_10y" in fs.missing
    empty = build_curve_shape_features([NOM], datetime(2026, 10, 15, 9, 0, tzinfo=NY))
    assert empty.features == {}
    with pytest.raises(ValueError, match="timezone-aware"):
        build_curve_shape_features([NOM], datetime(2026, 10, 17))
