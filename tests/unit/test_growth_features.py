"""Growth / activity features with GDP estimate stages (Task 3.5)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fakes import make_observation, monthly_series
from macrosignal.domain import ReleaseStage
from macrosignal.features.growth import (
    DecisionOverwriteError,
    FeatureDecisionLog,
    build_growth_features,
)
from macrosignal.features.series_registry import load_series_catalog
from macrosignal.pit.as_of import PitStore

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
CATALOG = load_series_catalog(
    ROOT / "configs/series/us_macro_v2.yaml", ROOT / "configs/series/release_map_v2.yaml"
)


def _gdp(q_start: date, q_end: date, value: float, released: datetime, stage: str):  # type: ignore[no-untyped-def]
    return make_observation(
        "GDPC1",
        q_start,
        q_end,
        value,
        released,
        stage=stage,
        frequency="quarterly",
        units="billions_chained_2017_usd",
        seasonal_adjustment="seasonally_adjusted_annual_rate",
    )


Q1 = (date(2026, 1, 1), date(2026, 3, 31))
Q2 = (date(2026, 4, 1), date(2026, 6, 30))
GDP = [
    _gdp(*Q1, 20_000.0, datetime(2026, 4, 29, 8, 30, tzinfo=NY), "advance"),
    _gdp(*Q1, 20_010.0, datetime(2026, 5, 28, 8, 30, tzinfo=NY), "second"),
    _gdp(*Q1, 20_020.0, datetime(2026, 6, 25, 8, 30, tzinfo=NY), "third"),
    _gdp(*Q2, 20_200.0, datetime(2026, 7, 30, 8, 30, tzinfo=NY), "advance"),
    _gdp(*Q2, 20_150.0, datetime(2026, 8, 27, 8, 30, tzinfo=NY), "second"),
]
INDPRO = monthly_series(
    "INDPRO",
    [100.0 + 0.1 * i for i in range(18)],
    start=(2025, 1),
    release_day=16,
    release_time=(23, 59),
    precision="release_date_only",
)


def _store() -> PitStore:
    return PitStore(GDP + INDPRO)


def test_gdp_stage_known_at_each_time() -> None:
    store = _store()

    def gdp_at(t: datetime) -> tuple[ReleaseStage, float, date]:
        f = build_growth_features(store, CATALOG, t).features["real_gdp__level"]
        return f.release_stage, f.value, f.reference_start

    assert gdp_at(datetime(2026, 5, 1, tzinfo=NY)) == (ReleaseStage.ADVANCE, 20_000.0, Q1[0])
    assert gdp_at(datetime(2026, 6, 1, tzinfo=NY)) == (ReleaseStage.SECOND, 20_010.0, Q1[0])
    assert gdp_at(datetime(2026, 7, 1, tzinfo=NY)) == (ReleaseStage.THIRD, 20_020.0, Q1[0])
    assert gdp_at(datetime(2026, 8, 1, tzinfo=NY)) == (ReleaseStage.ADVANCE, 20_200.0, Q2[0])
    assert gdp_at(datetime(2026, 9, 1, tzinfo=NY)) == (ReleaseStage.SECOND, 20_150.0, Q2[0])


def test_annualized_growth_uses_as_of_vintages() -> None:
    fs = build_growth_features(_store(), CATALOG, datetime(2026, 8, 1, tzinfo=NY))
    # Q2 advance vs Q1 third estimate (the Q1 vintage public on 1 Aug).
    assert fs.value("real_gdp__qoq_annualized") == pytest.approx(100 * ((20_200 / 20_020) ** 4 - 1))
    f = fs.features["real_gdp__qoq_annualized"]
    assert (f.reference_start, f.reference_end) == Q2
    assert f.units == "percent_annualized"
    assert f.stale_after_days == 150


def test_later_estimate_cannot_overwrite_past_decision() -> None:
    log = FeatureDecisionLog()
    t = datetime(2026, 5, 15, tzinfo=NY)
    first = build_growth_features(PitStore(GDP[:1] + INDPRO), CATALOG, t)
    log.record(first)
    # The full store now contains the second/third estimates, but they were not public at t.
    recomputed = build_growth_features(_store(), CATALOG, t)
    assert log.record(recomputed) == log.fingerprint(first)
    assert log.get("growth", t).value("real_gdp__level") == 20_000.0
    tampered = recomputed.model_copy(
        update={
            "features": {
                **recomputed.features,
                "real_gdp__level": recomputed.features["real_gdp__level"].model_copy(
                    update={"value": 20_020.0}
                ),
            }
        }
    )
    with pytest.raises(DecisionOverwriteError, match="already decided"):
        log.record(tampered)
    assert len(log) == 1


def test_activity_series_with_date_level_timing() -> None:
    fs = build_growth_features(_store(), CATALOG, datetime(2026, 5, 17, 9, 0, tzinfo=NY))
    f = fs.features["industrial_production__yoy_pct"]
    assert f.reference_start == date(2026, 4, 1)
    assert f.availability_precision.value == "release_date_only"
    morning_of_release = build_growth_features(
        _store(), CATALOG, datetime(2026, 5, 16, 12, 0, tzinfo=NY)
    )
    assert morning_of_release.features["industrial_production__level"].reference_start == date(
        2026, 3, 1
    )
