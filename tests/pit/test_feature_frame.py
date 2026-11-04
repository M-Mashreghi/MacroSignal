"""Ragged-edge AsOfFeatureFrame (Task 3.9)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fakes import monthly_series
from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.data.treasury import CurveType, parse_treasury_csv
from macrosignal.features.curve_shape import build_curve_shape_features
from macrosignal.features.frame import (
    PanelCell,
    SourceKind,
    build_feature_frame,
    cells_from_curve_shape,
    cells_from_feature_set,
)
from macrosignal.features.inflation import build_inflation_features
from macrosignal.features.labor import build_labor_features
from macrosignal.features.series_registry import load_series_catalog
from macrosignal.pit.as_of import PitStore

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
CATALOG = load_series_catalog(
    ROOT / "configs/series/us_macro_v2.yaml", ROOT / "configs/series/release_map_v2.yaml"
)
CPI = monthly_series("CPIAUCSL", [100.0 + i for i in range(22)], start=(2025, 1), release_day=15)
PAY = monthly_series(
    "PAYEMS", [150_000.0 + 50 * i for i in range(22)], start=(2025, 1), release_day=6
)
STORE = PitStore(CPI + PAY)
CURVE = parse_treasury_csv(
    (ROOT / "tests/fixtures/treasury/nominal.csv").read_text("utf-8"),
    CurveType.NOMINAL,
    snapshot_id="raw_nom",
    retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
)
CAL = UsTradingCalendar()
TIMES = [
    datetime.combine(d, datetime.min.time().replace(hour=9), tzinfo=NY)
    for d in CAL.sessions(date(2026, 10, 13), date(2026, 10, 20))
]


def _sources():  # type: ignore[no-untyped-def]
    return [
        lambda t: cells_from_feature_set(build_inflation_features(STORE, CATALOG, t)),
        lambda t: cells_from_feature_set(build_labor_features(STORE, CATALOG, t).features),
        lambda t: cells_from_curve_shape(
            build_curve_shape_features([CURVE], t), stale_after_days=2
        ),
    ]


def test_panel_keeps_original_age_for_carried_values() -> None:
    frame = build_feature_frame(TIMES, _sources())
    cpi = frame.feature("headline_cpi__level")
    assert [c.reference_start for c in cpi] == [date(2026, 8, 1)] * 2 + [date(2026, 9, 1)] * 4
    # Carried value: same available_at, age grows day by day.
    assert cpi[0].available_at == cpi[1].available_at
    assert cpi[1].age_since_available - cpi[0].age_since_available == timedelta(days=1)
    assert cpi[2].available_at == datetime(2026, 10, 15, 8, 30, tzinfo=NY)
    assert [c.updated_since_previous for c in cpi] == [True, False, True, False, False, False]


def test_heterogeneous_ages_visible() -> None:
    frame = build_feature_frame(TIMES, _sources())
    row = frame.row(TIMES[-1])
    ages = {n: c.age_since_reference_days for n, c in row.items() if c.kind is SourceKind.MACRO}
    assert ages["headline_cpi__level"] < ages["payrolls__level"] + 31
    assert row["nominal_level_10y"].kind is SourceKind.CURVE_SHAPE
    assert row["nominal_level_10y"].observation_date == date(2026, 10, 16)
    assert row["nominal_level_10y"].stale  # curve ends 10/16 EOD; 3+ days old > 2-day threshold
    assert frame.stale_share(TIMES[-1]) > 0


def test_missing_kept_explicit_per_time() -> None:
    frame = build_feature_frame(TIMES, _sources())
    first = frame.missing[TIMES[0].isoformat()]
    assert "pce_price__level" in first
    assert "nominal_level_10y" in first  # no curve knowable before 10/15 end of day
    assert "nominal_level_10y" not in frame.missing[TIMES[-1].isoformat()]


def test_records_and_dataframe() -> None:
    frame = build_feature_frame(TIMES[:2], _sources())
    df = frame.to_dataframe()
    assert {
        "feature_name",
        "value",
        "available_at",
        "age_since_available",
        "stale",
        "updated_since_previous",
    } <= set(df.columns)
    assert len(df) == len(frame.cells)
    assert "headline_cpi__yoy_pct" in frame.feature_names


def test_guards() -> None:
    t = TIMES[0]
    future = PanelCell(
        as_of=t,
        feature_name="x",
        kind=SourceKind.MACRO,
        value=1.0,
        available_at=t + timedelta(hours=1),
        availability_precision="exact_timestamp",
        age_since_available=timedelta(hours=-1),
        stale=False,
    )
    with pytest.raises(ValueError, match="lookahead"):
        build_feature_frame([t], [lambda _t: ([future], [])])
    ok = future.model_copy(update={"available_at": t, "age_since_available": timedelta(0)})
    with pytest.raises(ValueError, match="duplicate"):
        build_feature_frame([t], [lambda _t: ([ok, ok], [])])
    with pytest.raises(ValueError, match="different time"):
        build_feature_frame([TIMES[1]], [lambda _t: ([ok], [])])
    with pytest.raises(ValueError, match="strictly increasing"):
        build_feature_frame([TIMES[1], TIMES[0]], [])
    with pytest.raises(ValueError, match="timezone-aware"):
        build_feature_frame([datetime(2026, 10, 13)], [])
