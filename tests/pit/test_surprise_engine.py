"""Raw surprise / forecast-error engine (Task 3.13)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from fakes import make_observation, monthly_series
from macrosignal.domain import (
    ConsensusExpectation,
    ExpectationType,
    ReleaseEvent,
    SurpriseMode,
)
from macrosignal.features.series_registry import load_series_catalog
from macrosignal.pit.as_of import PitStore
from macrosignal.surprises.engine import SurpriseStatus, UnitsMismatchError, compute_surprise
from macrosignal.surprises.expectations import ExpectationService, StaticExpectationProvider
from macrosignal.surprises.forecast_baseline import BaselineModel, forecast_release

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
CATALOG = load_series_catalog(
    ROOT / "configs/series/us_macro_v2.yaml", ROOT / "configs/series/release_map_v2.yaml"
)
CPI_SERIES = CATALOG.get("headline_cpi")
LEVELS = [100.0 + 0.3 * i for i in range(26)]
CPI = monthly_series("CPIAUCSL", LEVELS, start=(2024, 1), release_day=12)
REL_AT = datetime(2026, 3, 12, 8, 30, tzinfo=NY)
EVENT = ReleaseEvent(
    release_id="CPI-2026-02",
    release_family="CPI",
    release_name="CPI",
    source="bls",
    calendar_snapshot_id="cal",
    source_timezone="America/New_York",
    scheduled_at=REL_AT,
    actual_release_at=REL_AT,
    reference_start=date(2026, 2, 1),
    reference_end=date(2026, 2, 28),
    release_stage="initial",
)
ACTUAL_MOM = 100 * (LEVELS[25] / LEVELS[24] - 1)


def _consensus(value: float, ts: datetime, units: str = "percent_mom") -> ConsensusExpectation:
    data: dict[str, Any] = {
        "release_id": "CPI-2026-02",
        "reference_start": date(2026, 2, 1),
        "reference_end": date(2026, 2, 28),
        "expected_value": value,
        "units": units,
        "expectation_source": "survey",
        "forecast_created_at": ts,
        "availability": {"available_at": ts, "precision": "provider_timestamp"},
        "source_snapshot_id": "cons_1",
    }
    return ConsensusExpectation.model_validate(data)


def _service(*cons: ConsensusExpectation, forecasts: tuple = ()) -> ExpectationService:  # type: ignore[type-arg]
    return ExpectationService(
        [
            StaticExpectationProvider("consensus", ExpectationType.CONSENSUS, cons),
            StaticExpectationProvider("baseline", ExpectationType.MODEL_FORECAST, forecasts),
        ]
    )


def test_market_surprise_from_pre_release_consensus() -> None:
    svc = _service(_consensus(0.25, REL_AT - timedelta(days=3)))
    rec = compute_surprise(
        PitStore(CPI), CPI_SERIES, "mom_pct", EVENT, svc, SurpriseMode.MARKET_SURPRISE
    )
    assert rec.status is SurpriseStatus.COMPUTED
    assert rec.label == "market_surprise" and rec.expectation_type is ExpectationType.CONSENSUS
    assert rec.actual == pytest.approx(ACTUAL_MOM)
    assert rec.raw_surprise == pytest.approx(ACTUAL_MOM - 0.25)
    assert rec.actual_available_at == REL_AT and rec.actual_stage == "initial"


def test_forecast_error_is_labelled_as_such() -> None:
    fc = forecast_release(
        PitStore(CPI), CPI_SERIES, "mom_pct", EVENT, BaselineModel("naive", min_train=1)
    )
    assert fc.forecast is not None
    svc = _service(forecasts=(fc.forecast,))
    rec = compute_surprise(
        PitStore(CPI), CPI_SERIES, "mom_pct", EVENT, svc, SurpriseMode.FORECAST_ERROR
    )
    assert rec.label == "forecast_error" and rec.expectation_type is ExpectationType.MODEL_FORECAST
    assert rec.raw_surprise == pytest.approx(ACTUAL_MOM - fc.forecast.expected_value)
    market = compute_surprise(
        PitStore(CPI), CPI_SERIES, "mom_pct", EVENT, svc, SurpriseMode.MARKET_SURPRISE
    )
    assert market.status is SurpriseStatus.MISSING_EXPECTATION and market.raw_surprise is None


def test_missing_expectation_never_fabricated() -> None:
    late = _consensus(0.25, REL_AT + timedelta(minutes=1))
    rec = compute_surprise(
        PitStore(CPI), CPI_SERIES, "mom_pct", EVENT, _service(late), SurpriseMode.MARKET_SURPRISE
    )
    assert rec.status is SurpriseStatus.MISSING_EXPECTATION
    assert rec.actual is not None and rec.expected is None and rec.raw_surprise is None


def test_actual_is_initial_print_not_later_revision() -> None:
    rev = make_observation(
        "CPIAUCSL",
        date(2026, 2, 1),
        date(2026, 2, 28),
        150.0,
        datetime(2026, 4, 10, 8, 30, tzinfo=NY),
        stage="revision",
    )
    svc = _service(_consensus(0.25, REL_AT - timedelta(days=3)))
    rec = compute_surprise(
        PitStore(CPI + [rev]), CPI_SERIES, "mom_pct", EVENT, svc, SurpriseMode.MARKET_SURPRISE
    )
    assert rec.actual == pytest.approx(ACTUAL_MOM)


def test_missing_actual_and_unit_mismatch() -> None:
    svc = _service(_consensus(0.25, REL_AT - timedelta(days=3)))
    rec = compute_surprise(
        PitStore(CPI[:-1]), CPI_SERIES, "mom_pct", EVENT, svc, SurpriseMode.MARKET_SURPRISE
    )
    assert rec.status is SurpriseStatus.MISSING_ACTUAL and rec.actual is None
    bad = _service(_consensus(3.1, REL_AT - timedelta(days=3), units="percent_yoy"))
    with pytest.raises(UnitsMismatchError):
        compute_surprise(
            PitStore(CPI), CPI_SERIES, "mom_pct", EVENT, bad, SurpriseMode.MARKET_SURPRISE
        )


def test_gdp_stage_actual_matches_event_stage() -> None:
    gdp_series = CATALOG.get("real_gdp")
    q = (date(2026, 1, 1), date(2026, 3, 31))
    prev = (date(2025, 10, 1), date(2025, 12, 31))
    kw = {
        "frequency": "quarterly",
        "units": "bn",
        "seasonal_adjustment": "seasonally_adjusted_annual_rate",
    }
    obs = [
        make_observation(
            "GDPC1", *prev, 100.0, datetime(2026, 1, 29, 8, 30, tzinfo=NY), stage="initial", **kw
        ),
        make_observation(
            "GDPC1", *q, 101.0, datetime(2026, 4, 29, 8, 30, tzinfo=NY), stage="initial", **kw
        ),
        make_observation(
            "GDPC1", *q, 101.5, datetime(2026, 5, 28, 8, 30, tzinfo=NY), stage="second", **kw
        ),
    ]
    second_at = datetime(2026, 5, 28, 8, 30, tzinfo=NY)
    second = ReleaseEvent(
        release_id="GDP-2026Q1-second",
        release_family="GDP",
        release_name="GDP",
        source="bea",
        calendar_snapshot_id="cal",
        source_timezone="America/New_York",
        scheduled_at=second_at,
        actual_release_at=second_at,
        reference_start=q[0],
        reference_end=q[1],
        release_stage="second",
    )
    rec = compute_surprise(
        PitStore(obs), gdp_series, "level", second, _service(), SurpriseMode.MARKET_SURPRISE
    )
    assert rec.actual == 101.5 and rec.actual_stage == "second"
    advance = second.model_copy(
        update={"release_id": "GDP-2026Q1-advance", "release_stage": "advance"}
    )
    assert (
        compute_surprise(
            PitStore(obs), gdp_series, "level", advance, _service(), SurpriseMode.MARKET_SURPRISE
        ).actual
        == 101.0
    )
    with pytest.raises(ValueError, match="belongs to GDP"):
        compute_surprise(
            PitStore(obs), gdp_series, "level", EVENT, _service(), SurpriseMode.MARKET_SURPRISE
        )
