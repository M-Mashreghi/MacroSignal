"""Policy / rates features (Task 3.6)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fakes import monthly_series
from macrosignal.calendar.fomc import parse_fomc_schedule
from macrosignal.data.treasury import CurveType, parse_treasury_csv
from macrosignal.features.inflation import build_inflation_features
from macrosignal.features.policy_rates import build_policy_rates_features
from macrosignal.features.series_registry import load_series_catalog
from macrosignal.pit.as_of import PitStore

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures"
NY = ZoneInfo("America/New_York")
CATALOG = load_series_catalog(
    ROOT / "configs/series/us_macro_v2.yaml", ROOT / "configs/series/release_map_v2.yaml"
)
CURVES = [
    parse_treasury_csv(
        (FIX / "treasury/nominal.csv").read_text("utf-8"),
        CurveType.NOMINAL,
        snapshot_id="raw_t_nom",
        retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
    ),
    parse_treasury_csv(
        (FIX / "treasury/real.csv").read_text("utf-8"),
        CurveType.REAL,
        snapshot_id="raw_t_real",
        retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
    ),
]
FOMC = parse_fomc_schedule(
    (FIX / "fomc/schedule.csv").read_text("utf-8"),
    retrieved_at=datetime(2026, 11, 4, 12, tzinfo=UTC),
)
FEDFUNDS = monthly_series(
    "FEDFUNDS",
    [4.33, 4.33, 4.30, 4.10, 4.09, 3.88, 3.87, 3.87, 3.86, 3.64],
    start=(2026, 1),
    release_day=1,
    release_time=(23, 59),
    precision="release_date_only",
    units="percent",
)
CPI = monthly_series("CPIAUCSL", [100.0 + i for i in range(10)], start=(2026, 1), release_day=16)


def _build(t: datetime, stale_days: int = 4):  # type: ignore[no-untyped-def]
    return build_policy_rates_features(
        PitStore(FEDFUNDS + CPI),
        CATALOG,
        t,
        curves=CURVES,
        meetings=FOMC.meetings,
        rates_stale_after_days=stale_days,
    )


def test_morning_macro_release_sees_previous_days_curve() -> None:
    morning = datetime(2026, 10, 16, 9, 0, tzinfo=NY)  # CPI for Sep released 08:30 today
    fs = _build(morning)
    assert fs.rates["nominal_10y"].observation_date == date(2026, 10, 15)
    assert fs.rates["nominal_10y"].value == 4.02
    cpi = build_inflation_features(PitStore(FEDFUNDS + CPI), CATALOG, morning)
    assert cpi.features["headline_cpi__level"].reference_start == date(2026, 9, 1)
    next_day = _build(datetime(2026, 10, 17, 9, 0, tzinfo=NY))
    assert next_day.rates["nominal_10y"].observation_date == date(2026, 10, 16)


def test_rate_feature_metadata_and_gaps() -> None:
    fs = _build(datetime(2026, 10, 17, 9, 0, tzinfo=NY))
    f = fs.rates["nominal_2y"]
    assert f.availability_precision.value == "inferred_eod"
    assert f.available_at == datetime(2026, 10, 16, 23, 59, 59, tzinfo=NY)
    assert f.snapshot_id == "raw_t_nom" and not f.stale
    assert fs.rates["real_10y"].value == 1.6
    assert {"real_3m", "real_2y"} <= set(fs.missing_rates)  # tenors the real curve lacks
    stale = _build(datetime(2026, 10, 25, tzinfo=NY), stale_days=4)
    assert stale.rates["nominal_10y"].stale


def test_policy_rate_from_registry_family() -> None:
    fs = _build(datetime(2026, 10, 17, 9, 0, tzinfo=NY))
    level = fs.policy.features["fed_funds__level"]
    assert level.reference_start == date(2026, 9, 1) and level.value == 3.86
    assert fs.policy.value("fed_funds__mom_diff") == pytest.approx(-0.01)
    assert level.availability_precision.value == "release_date_only"


def test_fomc_markers_without_surprise() -> None:
    before = _build(datetime(2026, 10, 28, 13, 0, tzinfo=NY)).fomc
    assert before.last_statement_id == "FOMC-2026-09-16"
    assert before.next_meeting_id == "FOMC-2026-10-28"
    assert before.days_to_next_statement == pytest.approx(1 / 24)
    assert not before.statement_released_today
    after = _build(datetime(2026, 10, 28, 15, 0, tzinfo=NY)).fomc
    assert after.last_statement_id == "FOMC-2026-10-28" and after.statement_released_today
    assert after.next_meeting_id == "FOMC-2026-12-09"
    assert after.calendar_snapshot_id == FOMC.calendar_snapshot_id
    assert not hasattr(after, "surprise")


def test_all_rates_respect_golden_rule() -> None:
    for day in range(14, 22):
        t = datetime(2026, 10, day, 9, 0, tzinfo=NY)
        fs = _build(t)
        assert all(r.available_at <= t for r in fs.rates.values())
