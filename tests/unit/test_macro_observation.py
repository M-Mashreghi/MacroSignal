"""MacroObservation / AvailabilityStamp contract and chronology guards."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from macrosignal.domain import (
    AvailabilityPrecision,
    AvailabilityStamp,
    Frequency,
    MacroObservation,
    ReleaseStage,
    SeasonalAdjustment,
)

ROOT = Path(__file__).resolve().parents[2]
ET = timezone(timedelta(hours=-4))


def _cpi(**overrides: Any) -> dict[str, Any]:
    """September 2026 CPI, first printed 2026-10-15 08:30 ET."""
    data: dict[str, Any] = {
        "source": "fred_alfred",
        "series_id": "CPIAUCSL",
        "retrieved_at": datetime(2026, 10, 20, 12, 0, tzinfo=UTC),
        "source_snapshot_id": "snap_cpi_001",
        "adapter_version": "0.1.0",
        "release_family": "CPI",
        "release_id": "CPI-2026-09",
        "release_stage": "initial",
        "reference_start": date(2026, 9, 1),
        "reference_end": date(2026, 9, 30),
        "value": 320.5,
        "units": "index_1982_1984_100",
        "frequency": "monthly",
        "seasonal_adjustment": "seasonally_adjusted",
        "release_timestamp": datetime(2026, 10, 15, 8, 30, tzinfo=ET),
        "availability": {
            "available_at": datetime(2026, 10, 15, 8, 30, tzinfo=ET),
            "precision": "exact_timestamp",
        },
        "vintage_date": date(2026, 10, 15),
        "realtime_start": date(2026, 10, 15),
        "realtime_end": date(9999, 12, 31),
    }
    data.update(overrides)
    return data


def _reject(match: str, **overrides: Any) -> None:
    with pytest.raises(ValidationError, match=match):
        MacroObservation.model_validate(_cpi(**overrides))


# --- valid construction -----------------------------------------------------------


def test_valid_observation_is_typed_and_frozen() -> None:
    obs = MacroObservation.model_validate(_cpi())
    assert obs.release_stage is ReleaseStage.INITIAL
    assert obs.frequency is Frequency.MONTHLY
    assert obs.seasonal_adjustment is SeasonalAdjustment.SEASONALLY_ADJUSTED
    assert obs.availability.precision is AvailabilityPrecision.EXACT_TIMESTAMP
    with pytest.raises(ValidationError, match="frozen"):
        obs.value = 1.0  # type: ignore[misc]


def test_round_trip_is_deterministic() -> None:
    obs = MacroObservation.model_validate(_cpi())
    again = MacroObservation.model_validate_json(obs.model_dump_json())
    assert again == obs
    assert again.model_dump_json() == obs.model_dump_json()


def test_vintage_fixture_rows_load() -> None:
    with (ROOT / "examples/vintage_fixture.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    observations = [
        MacroObservation.model_validate(
            _cpi(
                series_id=row["series_id"],
                release_id=None,
                release_stage="initial" if i == 0 else "revision",
                reference_start=row["reference_start"],
                reference_end="2026-08-31",
                value=row["value"],
                release_timestamp=row["available_at"],
                availability={"available_at": row["available_at"], "precision": "exact_timestamp"},
                vintage_date=row["vintage_date"],
                realtime_start=row["realtime_start"],
                realtime_end=row["realtime_end"],
            )
        )
        for i, row in enumerate(rows)
    ]
    first, revised = observations
    assert first.value == 100.0 and revised.value == 101.0
    assert first.realtime_end == date(2026, 9, 30) < revised.realtime_start  # type: ignore[operator]


def test_release_stage_fixture_quarterly_gdp_loads() -> None:
    with (ROOT / "examples/release_stage_fixture.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    stages = []
    for row in rows:
        obs = MacroObservation.model_validate(
            _cpi(
                series_id="GDPC1",
                release_family=row["release_family"],
                release_id=f"GDP-2026Q2-{row['release_stage']}",
                release_stage=row["release_stage"],
                reference_start=date(2026, 4, 1),
                reference_end=date(2026, 6, 30),
                value=row["value"],
                units="billions_chained_2017_usd",
                frequency="quarterly",
                seasonal_adjustment="seasonally_adjusted_annual_rate",
                release_timestamp=row["released_at"],
                availability={"available_at": row["released_at"], "precision": "exact_timestamp"},
                vintage_date=None,
                realtime_start=None,
                realtime_end=None,
            )
        )
        stages.append(obs.release_stage)
    assert stages == [ReleaseStage.ADVANCE, ReleaseStage.SECOND, ReleaseStage.THIRD]


def test_daily_series_may_be_available_on_reference_date() -> None:
    obs = MacroObservation.model_validate(
        _cpi(
            series_id="DGS10",
            release_family=None,
            release_id=None,
            reference_start=date(2026, 10, 15),
            reference_end=date(2026, 10, 15),
            frequency="daily",
            seasonal_adjustment="not_seasonally_adjusted",
            release_timestamp=None,
            availability={
                "available_at": datetime(2026, 10, 15, 23, 59, tzinfo=ET),
                "precision": "inferred_eod",
            },
            vintage_date=None,
            realtime_start=None,
            realtime_end=None,
        )
    )
    assert obs.availability.precision is AvailabilityPrecision.INFERRED_EOD


def test_conservative_availability_later_than_release_is_allowed() -> None:
    obs = MacroObservation.model_validate(
        _cpi(
            availability={
                "available_at": datetime(2026, 10, 15, 23, 59, tzinfo=ET),
                "precision": "inferred_eod",
            }
        )
    )
    assert obs.availability.available_at > obs.release_timestamp  # type: ignore[operator]


# --- point-in-time ----------------------------------------------------------------


def test_is_available_at_applies_golden_rule() -> None:
    obs = MacroObservation.model_validate(_cpi())
    release = datetime(2026, 10, 15, 8, 30, tzinfo=ET)
    assert not obs.is_available_at(release - timedelta(seconds=1))
    assert obs.is_available_at(release)
    assert obs.is_available_at(release.astimezone(UTC))


def test_is_available_at_rejects_naive_decision_time() -> None:
    obs = MacroObservation.model_validate(_cpi())
    with pytest.raises(ValueError, match="timezone-aware"):
        obs.is_available_at(datetime(2026, 10, 16, 9, 0))


# --- availability stamp -----------------------------------------------------------


def test_naive_date_is_not_an_availability_stamp() -> None:
    _reject("availability", availability=date(2026, 10, 15))


def test_naive_available_at_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        AvailabilityStamp(available_at=datetime(2026, 10, 15, 8, 30), precision="exact_timestamp")


@pytest.mark.parametrize("precision", ["exact", "date", "EXACT_TIMESTAMP", "", "midnight"])
def test_unsupported_precision_rejected(precision: str) -> None:
    with pytest.raises(ValidationError, match="precision"):
        AvailabilityStamp(
            available_at=datetime(2026, 10, 15, 8, 30, tzinfo=ET), precision=precision
        )


def test_precision_vocabulary_matches_data_contract() -> None:
    assert {p.value for p in AvailabilityPrecision} == {
        "exact_timestamp",
        "provider_timestamp",
        "release_date_only",
        "inferred_eod",
        "unknown",
    }


def test_availability_stamp_requires_precision_and_forbids_extras() -> None:
    with pytest.raises(ValidationError, match="precision"):
        AvailabilityStamp.model_validate({"available_at": datetime(2026, 1, 1, tzinfo=UTC)})
    with pytest.raises(ValidationError, match="extra"):
        AvailabilityStamp.model_validate(
            {
                "available_at": datetime(2026, 1, 1, tzinfo=UTC),
                "precision": "unknown",
                "guess": True,
            }
        )


# --- impossible chronology --------------------------------------------------------


def test_available_before_reference_period_end_rejected() -> None:
    _reject(
        "not after the reference period end",
        availability={
            "available_at": datetime(2026, 9, 15, 8, 30, tzinfo=ET),
            "precision": "exact_timestamp",
        },
        release_timestamp=None,
        vintage_date=None,
        realtime_start=None,
        realtime_end=None,
    )


def test_monthly_value_not_available_on_last_day_of_month() -> None:
    _reject(
        "not after the reference period end",
        availability={
            "available_at": datetime(2026, 9, 30, 23, 0, tzinfo=ET),
            "precision": "exact_timestamp",
        },
        release_timestamp=None,
        vintage_date=None,
        realtime_start=None,
        realtime_end=None,
    )


def test_release_before_reference_end_rejected() -> None:
    _reject("release_timestamp .* not after", release_timestamp=datetime(2026, 9, 20, tzinfo=ET))


def test_available_before_release_rejected() -> None:
    _reject(
        "precedes release_timestamp",
        availability={
            "available_at": datetime(2026, 10, 15, 8, 0, tzinfo=ET),
            "precision": "exact_timestamp",
        },
    )


def test_naive_release_timestamp_rejected() -> None:
    _reject("release_timestamp", release_timestamp=datetime(2026, 10, 15, 8, 30))


def test_naive_retrieved_at_rejected() -> None:
    _reject("retrieved_at", retrieved_at=datetime(2026, 10, 20, 12, 0))


def test_retrieved_before_available_rejected() -> None:
    _reject("retrieved_at precedes", retrieved_at=datetime(2026, 10, 15, 8, 0, tzinfo=ET))


def test_reference_end_before_start_rejected() -> None:
    _reject("reference_end is before reference_start", reference_end=date(2026, 8, 31))


@pytest.mark.parametrize(
    ("frequency", "start", "end"),
    [
        ("monthly", date(2026, 9, 2), date(2026, 9, 30)),
        ("monthly", date(2026, 9, 1), date(2026, 10, 31)),
        ("quarterly", date(2026, 8, 1), date(2026, 10, 31)),
        ("quarterly", date(2026, 7, 1), date(2026, 9, 29)),
        ("annual", date(2025, 1, 1), date(2025, 12, 30)),
        ("weekly", date(2026, 9, 1), date(2026, 9, 30)),
        ("daily", date(2026, 9, 29), date(2026, 9, 30)),
    ],
)
def test_reference_period_must_match_frequency(frequency: str, start: date, end: date) -> None:
    _reject("is not a single", frequency=frequency, reference_start=start, reference_end=end)


def test_realtime_end_before_start_rejected() -> None:
    _reject("realtime_end is before realtime_start", realtime_end=date(2026, 10, 14))


def test_realtime_end_without_start_rejected() -> None:
    _reject("realtime_end requires realtime_start", realtime_start=None)


def test_available_before_vintage_date_rejected() -> None:
    _reject("before vintage_date", vintage_date=date(2026, 10, 16), realtime_start=None,
            realtime_end=None)


def test_vintage_before_reference_end_rejected() -> None:
    _reject("vintage_date .* before reference_end", vintage_date=date(2026, 9, 15))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_value_rejected(value: float) -> None:
    _reject("value", value=value)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("release_stage", "final"),
        ("frequency", "biweekly"),
        ("seasonal_adjustment", "sa"),
        ("release_family", "cpi"),
        ("source_snapshot_id", ""),
        ("adapter_version", ""),
    ],
)
def test_invalid_metadata_rejected(field: str, bad: str) -> None:
    _reject(field, **{field: bad})


@pytest.mark.parametrize(
    "missing",
    ["source", "series_id", "retrieved_at", "source_snapshot_id", "adapter_version",
     "availability", "units", "release_stage"],
)
def test_provenance_fields_are_required(missing: str) -> None:
    data = _cpi()
    del data[missing]
    with pytest.raises(ValidationError, match=missing):
        MacroObservation.model_validate(data)


def test_unknown_field_rejected() -> None:
    _reject("extra", revised_value=321.0)
