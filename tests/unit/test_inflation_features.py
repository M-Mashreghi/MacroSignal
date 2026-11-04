"""Inflation feature pipeline with PIT inputs and staleness (Task 3.3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fakes import make_observation, monthly_series
from macrosignal.domain import ReleaseStage
from macrosignal.features.as_of_features import AsOfFeature
from macrosignal.features.inflation import build_inflation_features
from macrosignal.features.series_registry import load_series_catalog
from macrosignal.pit.as_of import PitStore

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
CATALOG = load_series_catalog(
    ROOT / "configs/series/us_macro_v2.yaml", ROOT / "configs/series/release_map_v2.yaml"
)

# 14 synthetic monthly CPI prints, Jan-2025 .. Feb-2026, released on the 12th at 08:30 ET.
CPI = monthly_series("CPIAUCSL", [100.0 + i for i in range(14)])
CORE = monthly_series("CPILFESL", [200.0 + 2 * i for i in range(14)])


def _store(*extra: list) -> PitStore:  # type: ignore[type-arg]
    return PitStore([*CPI, *CORE, *[o for e in extra for o in e]])


def test_features_use_only_released_data() -> None:
    store = _store()
    before = build_inflation_features(store, CATALOG, datetime(2026, 3, 12, 8, 29, tzinfo=NY))
    after = build_inflation_features(store, CATALOG, datetime(2026, 3, 12, 8, 30, tzinfo=NY))
    assert before.features["headline_cpi__level"].reference_start == date(2026, 1, 1)
    assert after.features["headline_cpi__level"].reference_start == date(2026, 2, 1)
    assert after.value("headline_cpi__level") == 113.0
    assert after.value("headline_cpi__mom_pct") == pytest.approx(100 * (113 / 112 - 1))
    assert after.value("headline_cpi__yoy_pct") == pytest.approx(100 * (113 / 101 - 1))
    assert before.value("headline_cpi__yoy_pct") == pytest.approx(12.0)
    assert after.value("core_cpi__yoy_pct") == pytest.approx(100 * (226 / 202 - 1))


def test_age_and_staleness_metadata() -> None:
    t = datetime(2026, 3, 20, 9, 0, tzinfo=NY)
    f: AsOfFeature = build_inflation_features(_store(), CATALOG, t).features[
        "headline_cpi__mom_pct"
    ]
    assert f.available_at == datetime(2026, 3, 12, 8, 30, tzinfo=NY)
    assert f.age_since_available == t - f.available_at
    assert f.age_since_reference_days == (date(2026, 3, 20) - date(2026, 2, 28)).days
    assert f.stale_after_days == 50 and not f.stale
    late = build_inflation_features(_store(), CATALOG, datetime(2026, 5, 1, tzinfo=NY))
    assert late.features["headline_cpi__level"].stale  # 62 days after Feb ended
    assert "headline_cpi__level" in late.stale_features
    assert f.release_stage is ReleaseStage.INITIAL
    assert (
        f.input_snapshot_ids == tuple(sorted(f.input_snapshot_ids))
        and len(f.input_snapshot_ids) == 2
    )


def test_missing_series_reported_not_filled() -> None:
    fs = build_inflation_features(_store(), CATALOG, datetime(2026, 3, 20, tzinfo=NY))
    assert "pce_price__level" in fs.missing and "core_pce_price__yoy_pct" in fs.missing
    assert "pce_price__level" not in fs.features
    early = build_inflation_features(_store(), CATALOG, datetime(2025, 6, 1, tzinfo=NY))
    assert "headline_cpi__yoy_pct" in early.missing  # needs 12 months of history
    assert early.value("headline_cpi__mom_pct") is not None


def test_revision_used_only_after_its_release() -> None:
    revised = make_observation(
        "CPIAUCSL",
        date(2026, 2, 1),
        date(2026, 2, 28),
        113.5,
        datetime(2026, 4, 10, 8, 30, tzinfo=NY),
        stage="revision",
    )
    store = _store([revised])
    mid = build_inflation_features(store, CATALOG, datetime(2026, 4, 1, tzinfo=NY))
    assert mid.value("headline_cpi__level") == 113.0
    later = build_inflation_features(store, CATALOG, datetime(2026, 4, 10, 9, 0, tzinfo=NY))
    assert later.value("headline_cpi__level") == 113.5
    assert later.features["headline_cpi__level"].release_stage is ReleaseStage.REVISION


def test_gap_in_latest_period_is_missing_not_backfilled() -> None:
    gappy = [o for o in CPI if o.reference_start != date(2026, 1, 1)]
    fs = build_inflation_features(PitStore(gappy + CORE), CATALOG, datetime(2026, 3, 20, tzinfo=NY))
    assert fs.value("headline_cpi__level") == 113.0
    assert "headline_cpi__mom_pct" in fs.missing  # Feb has no Jan input


def test_all_features_respect_golden_rule() -> None:
    store = _store()
    t = datetime(2025, 12, 1, tzinfo=NY)
    while t < datetime(2026, 4, 1, tzinfo=NY):
        fs = build_inflation_features(store, CATALOG, t)
        assert all(f.available_at <= t for f in fs.features.values())
        t += timedelta(days=3, hours=5)


def test_naive_time_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_inflation_features(_store(), CATALOG, datetime(2026, 3, 20))
