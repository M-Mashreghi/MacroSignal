"""Pre-release forecast baselines (Task 3.12)."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from fakes import make_observation, monthly_series
from macrosignal.domain import ExpectationType, ReleaseEvent, SurpriseMode, check_pre_release
from macrosignal.features.series_registry import load_series_catalog
from macrosignal.pit.as_of import PitStore
from macrosignal.surprises.forecast_baseline import (
    BaselineModel,
    forecast_release,
    rolling_forecasts,
)

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
CATALOG = load_series_catalog(
    ROOT / "configs/series/us_macro_v2.yaml", ROOT / "configs/series/release_map_v2.yaml"
)
SERIES = CATALOG.get("headline_cpi")
LEVELS = [100.0 * (1.002**i) * (1 + 0.001 * ((-1) ** i)) for i in range(30)]
CPI = monthly_series("CPIAUCSL", LEVELS, start=(2024, 1), release_day=12)


def _event(year: int, month: int) -> ReleaseEvent:
    end = date(year, month, calendar.monthrange(year, month)[1])
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    at = datetime(ny, nm, 12, 8, 30, tzinfo=NY)
    return ReleaseEvent(
        release_id=f"CPI-{year}-{month:02d}",
        release_family="CPI",
        release_name="CPI",
        source="bls",
        calendar_snapshot_id="cal",
        source_timezone="America/New_York",
        scheduled_at=at,
        actual_release_at=at,
        reference_start=date(year, month, 1),
        reference_end=end,
        release_stage="initial",
    )


def test_naive_forecast_is_last_known_value_before_release() -> None:
    store = PitStore(CPI)
    res = forecast_release(
        store, SERIES, "mom_pct", _event(2026, 3), BaselineModel("naive", min_train=1)
    )
    f = res.forecast
    assert f is not None and res.label == "forecast_error"
    assert f.expectation_type is ExpectationType.MODEL_FORECAST
    feb = 100 * (LEVELS[25] / LEVELS[24] - 1)
    assert f.expected_value == pytest.approx(feb)
    assert f.forecast_created_at == datetime(2026, 4, 11, 8, 30, tzinfo=NY)
    assert f.training_cutoff == f.forecast_created_at
    assert f.model_version == "baseline-1:naive_last"
    check_pre_release(f, _event(2026, 3), SurpriseMode.FORECAST_ERROR)
    with pytest.raises(Exception, match="requires a consensus"):
        check_pre_release(f, _event(2026, 3), SurpriseMode.MARKET_SURPRISE)


def test_ar_matches_manual_least_squares() -> None:
    store = PitStore(CPI)
    model = BaselineModel("ar", lags=1, min_train=12)
    res = forecast_release(store, SERIES, "mom_pct", _event(2026, 3), model)
    y = np.array([100 * (LEVELS[i] / LEVELS[i - 1] - 1) for i in range(1, 26)])
    x = np.column_stack([np.ones(len(y) - 1), y[:-1]])
    beta, *_ = np.linalg.lstsq(x, y[1:], rcond=None)
    assert res.forecast is not None
    assert res.forecast.expected_value == pytest.approx(beta[0] + beta[1] * y[-1])
    assert res.n_train == 25
    ridge = forecast_release(
        store, SERIES, "mom_pct", _event(2026, 3), BaselineModel("ridge_ar", 1, 10.0)
    )
    assert ridge.forecast is not None and ridge.forecast.model_id == "ridge_ar1_a10"


def test_training_never_sees_target_or_later_revisions() -> None:
    # A huge revision of Feb-2026 published *after* the March release must not affect the forecast.
    late_rev = make_observation(
        "CPIAUCSL",
        date(2026, 2, 1),
        date(2026, 2, 28),
        999.0,
        datetime(2026, 4, 20, 8, 30, tzinfo=NY),
        stage="revision",
    )
    base = forecast_release(
        PitStore(CPI), SERIES, "mom_pct", _event(2026, 3), BaselineModel("ar", 1)
    )
    with_rev = forecast_release(
        PitStore(CPI + [late_rev]), SERIES, "mom_pct", _event(2026, 3), BaselineModel("ar", 1)
    )
    assert base.forecast is not None and with_rev.forecast is not None
    assert base.forecast.expected_value == with_rev.forecast.expected_value
    # A revision public *before* creation is legitimately used.
    early_rev = late_rev.model_copy(
        update={
            "availability": late_rev.availability.model_copy(
                update={"available_at": datetime(2026, 4, 1, tzinfo=NY)}
            )
        }
    )
    used = forecast_release(
        PitStore(CPI + [early_rev]),
        SERIES,
        "mom_pct",
        _event(2026, 3),
        BaselineModel("naive", min_train=1),
    )
    assert used.forecast is not None and used.forecast.expected_value > 100


def test_rolling_origin_and_insufficient_history() -> None:
    events = [_event(2024, m) for m in (3, 4)] + [_event(2025, 6), _event(2025, 7)]
    out = rolling_forecasts(
        PitStore(CPI), SERIES, "mom_pct", reversed(events), BaselineModel("ar", 1)
    )
    assert [o.release_id for o in out] == [e.release_id for e in events]
    assert out[0].forecast is None and "training values" in (out[0].skipped_reason or "")
    assert out[2].forecast is not None and out[3].forecast is not None
    assert out[3].n_train == out[2].n_train + 1
    for o in out:
        if o.forecast:
            assert (
                o.forecast.training_cutoff
                < next(e for e in events if e.release_id == o.release_id).actual_release_at
            )  # type: ignore[operator]


def test_guards() -> None:
    pending = _event(2026, 3).model_copy(update={"actual_release_at": None})
    assert (
        forecast_release(PitStore(CPI), SERIES, "mom_pct", pending, BaselineModel("naive")).forecast
        is None
    )
    with pytest.raises(ValueError, match="lead must be positive"):
        forecast_release(
            PitStore(CPI),
            SERIES,
            "mom_pct",
            _event(2026, 3),
            BaselineModel("naive"),
            lead=timedelta(0),
        )
