"""Labor feature pipeline (Task 3.4)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from fakes import make_observation, monthly_series
from macrosignal.config import load_config_file
from macrosignal.config.models import MacroSeriesRegistry, ReleaseMap
from macrosignal.domain import ReleaseEvent, ReleaseStage
from macrosignal.features.labor import build_labor_features
from macrosignal.features.series_registry import build_series_catalog, load_series_catalog
from macrosignal.pit.as_of import PitStore

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
REG = ROOT / "configs/series/us_macro_v2.yaml"
RMAP = ROOT / "configs/series/release_map_v2.yaml"
CATALOG = load_series_catalog(REG, RMAP)

# Employment Situation: synthetic prints released on the 6th of the next month, 08:30 ET.
PAYROLLS = monthly_series(
    "PAYEMS", [150_000.0 + 100 * i for i in range(6)], release_day=6, units="thousands_of_persons"
)
UNRATE = monthly_series("UNRATE", [4.0, 4.1, 4.1, 4.2, 4.3, 4.2], release_day=6, units="percent")


def _event(month: int, day: int = 6) -> ReleaseEvent:
    ref_month = month - 1
    return ReleaseEvent(
        release_id=f"ES-2025-{ref_month:02d}",
        release_family="EMPLOYMENT_SITUATION",
        release_name="Employment Situation",
        source="bls",
        calendar_snapshot_id="cal",
        source_timezone="America/New_York",
        scheduled_at=datetime(2025, month, day, 8, 30, tzinfo=NY),
        actual_release_at=datetime(2025, month, day, 8, 30, tzinfo=NY),
        reference_start=date(2025, ref_month, 1),
        reference_end=date(2025, ref_month, 28),
        release_stage="initial",
    )


def test_payroll_and_unemployment_features() -> None:
    store = PitStore(PAYROLLS + UNRATE)
    t = datetime(2025, 7, 6, 9, 0, tzinfo=NY)
    fs = build_labor_features(store, CATALOG, t, [_event(7)])
    assert fs.value("payrolls__level") == 150_500.0
    assert fs.value("payrolls__mom_diff") == pytest.approx(100.0)
    assert fs.value("unemployment__level") == 4.2
    assert fs.value("unemployment__mom_diff") == pytest.approx(-0.1)
    f = fs.features.features["payrolls__mom_diff"]
    assert f.units == "thousands_of_persons"
    assert f.stale_after_days == 45 and not f.stale
    assert f.age_since_available.total_seconds() == 30 * 60
    assert fs.latest_release is not None and fs.latest_release.release_id == "ES-2025-06"
    assert fs.overdue_features == ()


def test_revision_aware_inputs() -> None:
    # On 6 Jun the May print arrives together with a revision of April (150300 -> 150250).
    revised_apr = make_observation(
        "PAYEMS",
        date(2025, 4, 1),
        date(2025, 4, 30),
        150_250.0,
        datetime(2025, 6, 6, 8, 30, tzinfo=NY),
        stage="revision",
        units="thousands_of_persons",
    )
    store = PitStore(PAYROLLS + UNRATE + [revised_apr])
    before = build_labor_features(store, CATALOG, datetime(2025, 6, 6, 8, 29, tzinfo=NY))
    assert before.value("payrolls__mom_diff") == pytest.approx(100.0)  # Apr vs Mar, original
    after = build_labor_features(store, CATALOG, datetime(2025, 6, 6, 8, 30, tzinfo=NY))
    assert after.value("payrolls__level") == 150_400.0
    assert after.value("payrolls__mom_diff") == pytest.approx(150_400 - 150_250)
    assert after.features.features["payrolls__level"].release_stage is ReleaseStage.INITIAL


def test_overdue_when_release_happened_without_data() -> None:
    store = PitStore(PAYROLLS[:5] + UNRATE[:5])  # June data (released 6 Jul) missing
    fs = build_labor_features(
        store, CATALOG, datetime(2025, 7, 10, tzinfo=NY), [_event(6), _event(7)]
    )
    assert fs.latest_release is not None and fs.latest_release.release_id == "ES-2025-06"
    assert (
        "payrolls__level" in fs.overdue_features and "unemployment__mom_diff" in fs.overdue_features
    )
    # Scheduled-only events do not count as releases.
    pending = _event(7).model_copy(update={"actual_release_at": None})
    fs2 = build_labor_features(
        store, CATALOG, datetime(2025, 7, 10, tzinfo=NY), [_event(6), pending]
    )
    assert fs2.overdue_features == ()


def _catalog_with(mutate: Any):  # type: ignore[no-untyped-def]
    reg = load_config_file(REG, MacroSeriesRegistry).model_dump()
    rmap = load_config_file(RMAP, ReleaseMap).model_dump()
    mutate(reg, rmap)
    return build_series_catalog(
        MacroSeriesRegistry.model_validate(reg), ReleaseMap.model_validate(rmap)
    )


def test_labor_series_must_use_employment_situation_timing() -> None:
    def move(reg: dict[str, Any], rmap: dict[str, Any]) -> None:
        s = next(x for x in reg["series"] if x["key"] == "unemployment")
        s["release_family"] = "CPI"
        rmap["release_families"]["EMPLOYMENT_SITUATION"]["series_keys"].remove("unemployment")
        rmap["release_families"]["CPI"]["series_keys"].append("unemployment")

    with pytest.raises(ValueError, match="EMPLOYMENT_SITUATION"):
        build_labor_features(PitStore(), _catalog_with(move), datetime(2025, 7, 1, tzinfo=NY))
