"""Macro transformation registry arithmetic and provenance (Task 3.2)."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from macrosignal.domain import AvailabilityPrecision, Frequency, MacroObservation
from macrosignal.features.series_registry import KNOWN_TRANSFORMATIONS
from macrosignal.features.transformations import (
    FEATURE_VERSION,
    TRANSFORMATIONS,
    TransformationError,
    transform,
)

NY = ZoneInfo("America/New_York")


def _monthly(year: int, month: int, value: float, **kw: Any) -> MacroObservation:
    end = date(year, month, calendar.monthrange(year, month)[1])
    nm_year, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    released = datetime.combine(date(nm_year, nm, 12), time(8, 30), tzinfo=NY)
    data: dict[str, Any] = {
        "source": "synthetic",
        "series_id": "SYN",
        "retrieved_at": datetime(2030, 1, 1, tzinfo=UTC),
        "source_snapshot_id": f"snap_{year}_{month:02d}",
        "adapter_version": "t",
        "release_stage": "initial",
        "reference_start": date(year, month, 1),
        "reference_end": end,
        "value": value,
        "units": "index",
        "frequency": "monthly",
        "seasonal_adjustment": "seasonally_adjusted",
        "availability": {"available_at": released, "precision": "exact_timestamp"},
    }
    data.update(kw)
    return MacroObservation.model_validate(data)


def _year(values: list[float], start_year: int = 2025) -> list[MacroObservation]:
    out = []
    for i, v in enumerate(values):
        y, m = divmod(i, 12)
        out.append(_monthly(start_year + y, m + 1, v))
    return out


def test_registry_covers_series_vocabulary() -> None:
    assert set(TRANSFORMATIONS) == KNOWN_TRANSFORMATIONS


def test_level_and_differences() -> None:
    obs = _year([100.0, 101.0, 103.0])
    assert [v.value for v in transform(obs, "level", series_key="x")] == [100.0, 101.0, 103.0]
    assert [v.value for v in transform(obs, "mom_diff", series_key="x")] == [1.0, 2.0]
    assert [v.value for v in transform(obs, "level_diff", series_key="x")] == [1.0, 2.0]


def test_mom_pct_arithmetic() -> None:
    obs = _year([200.0, 202.0, 199.98])
    vals = [v.value for v in transform(obs, "mom_pct", series_key="x")]
    assert vals == pytest.approx([1.0, -1.0])


def test_yoy_pct_uses_twelve_month_lag() -> None:
    obs = _year([100.0 + i for i in range(14)])
    out = transform(obs, "yoy_pct", series_key="x")
    assert [v.reference_start for v in out] == [date(2026, 1, 1), date(2026, 2, 1)]
    assert out[0].value == pytest.approx(12.0)
    assert out[1].value == pytest.approx(100 * (113 / 101 - 1))
    assert out[0].units == "percent_yoy"


def _quarter(year: int, q: int, value: float) -> MacroObservation:
    first = 3 * q - 2
    end = date(year, first + 2, calendar.monthrange(year, first + 2)[1])
    released = datetime.combine(
        date(year + (q == 4), (first + 3) % 12 + 1, 28), time(8, 30), tzinfo=NY
    )
    return _monthly(
        2025,
        1,
        value,
        reference_start=date(year, first, 1),
        reference_end=end,
        frequency="quarterly",
        seasonal_adjustment="seasonally_adjusted_annual_rate",
        availability={"available_at": released, "precision": "exact_timestamp"},
    )


def test_quarterly_annualized_and_qoq() -> None:
    obs = [_quarter(2026, 1, 100.0), _quarter(2026, 2, 101.0)]
    ann = transform(obs, "qoq_annualized", series_key="gdp")
    assert ann[0].value == pytest.approx(100 * (1.01**4 - 1))
    assert ann[0].units == "percent_annualized"
    assert transform(obs, "qoq_pct", series_key="gdp")[0].value == pytest.approx(1.0)
    with pytest.raises(TransformationError, match="not defined for quarterly"):
        transform(obs, "mom_pct", series_key="gdp")


def test_gaps_are_not_interpolated() -> None:
    obs = _year([100.0, 101.0, 102.0, 103.0])
    del obs[2]
    out = transform(obs, "mom_pct", series_key="x")
    assert [v.reference_start for v in out] == [date(2025, 2, 1)]  # Apr has no Mar input


def test_non_positive_base_gives_no_value() -> None:
    obs = _year([0.0, 1.0])
    assert transform(obs, "mom_pct", series_key="x") == []


def test_provenance_carried_into_outputs() -> None:
    obs = _year([100.0, 101.0])
    obs[0] = obs[0].model_copy(
        update={
            "availability": obs[0].availability.model_copy(
                update={
                    "precision": AvailabilityPrecision.RELEASE_DATE_ONLY,
                    "available_at": datetime(2025, 2, 12, 23, 59, 59, tzinfo=NY),
                }
            )
        }
    )
    (v,) = transform(obs, "mom_pct", series_key="headline_cpi")
    assert v.feature_name == "headline_cpi__mom_pct"
    assert v.feature_version == FEATURE_VERSION
    assert v.seasonal_adjustment.value == "seasonally_adjusted"
    assert v.frequency is Frequency.MONTHLY
    # Available only when both inputs are; precision is the worst of the inputs.
    assert v.available_at == datetime(2025, 3, 12, 8, 30, tzinfo=NY)
    assert v.availability_precision is AvailabilityPrecision.RELEASE_DATE_ONLY
    assert v.input_snapshot_ids == ("snap_2025_01", "snap_2025_02")


def test_mixed_conventions_rejected() -> None:
    obs = _year([100.0, 101.0])
    obs[1] = _monthly(2025, 2, 101.0, units="percent")
    with pytest.raises(TransformationError, match="mixed units"):
        transform(obs, "mom_pct", series_key="x")
    obs = _year([100.0, 101.0])
    obs[1] = _monthly(2025, 2, 101.0, seasonal_adjustment="not_seasonally_adjusted")
    with pytest.raises(TransformationError, match="mixed seasonal_adjustment"):
        transform(obs, "mom_pct", series_key="x")
    with pytest.raises(TransformationError, match="several series"):
        transform([obs[0], _monthly(2025, 3, 1.0, series_id="OTHER")], "level", series_key="x")


def test_duplicate_vintages_and_unknown_names_rejected() -> None:
    obs = _year([100.0])
    with pytest.raises(TransformationError, match="several vintages"):
        transform(
            obs + [_monthly(2025, 1, 100.5, release_stage="revision")], "level", series_key="x"
        )
    with pytest.raises(TransformationError, match="unknown transformation"):
        transform(obs, "log_level", series_key="x")
    assert transform([], "level", series_key="x") == []
