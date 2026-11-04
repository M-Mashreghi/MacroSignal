"""Expectation types, provenance and pre-release chronology (Task 1.6)."""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from macrosignal.domain import (
    ConsensusExpectation,
    ExpectationChronologyError,
    ExpectationType,
    ModelForecast,
    ProxyExpectation,
    ReleaseEvent,
    SurpriseMode,
    check_pre_release,
    parse_expectation,
)

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
RELEASE_AT = datetime(2026, 10, 15, 8, 30, tzinfo=NY)


def _base(**overrides: Any) -> dict[str, Any]:
    created = datetime(2026, 10, 9, 17, 0, tzinfo=NY)
    data: dict[str, Any] = {
        "release_id": "CPI-2026-09",
        "reference_start": date(2026, 9, 1),
        "reference_end": date(2026, 9, 30),
        "expected_value": 0.3,
        "units": "percent_mom",
        "expectation_source": "user_consensus_csv",
        "forecast_created_at": created,
        "availability": {"available_at": created, "precision": "provider_timestamp"},
        "source_snapshot_id": "snap_exp_001",
    }
    data.update(overrides)
    return data


def _consensus(**kw: Any) -> ConsensusExpectation:
    return ConsensusExpectation.model_validate(_base(**kw))


def _forecast(**kw: Any) -> ModelForecast:
    data = _base(
        expectation_source="ar1_baseline",
        model_id="ar1_cpi_mom",
        model_version="0.1.0",
        training_cutoff=datetime(2026, 10, 9, 16, 0, tzinfo=NY),
    )
    data.update(kw)
    return ModelForecast.model_validate(data)


def _event(**kw: Any) -> ReleaseEvent:
    data: dict[str, Any] = {
        "release_id": "CPI-2026-09",
        "release_family": "CPI",
        "release_name": "Consumer Price Index",
        "source": "bls",
        "calendar_snapshot_id": "cal_001",
        "source_timezone": "America/New_York",
        "scheduled_at": RELEASE_AT,
        "actual_release_at": RELEASE_AT,
        "reference_start": date(2026, 9, 1),
        "reference_end": date(2026, 9, 30),
        "release_stage": "initial",
    }
    data.update(kw)
    return ReleaseEvent.model_validate(data)


def test_three_distinct_types() -> None:
    proxy = ProxyExpectation.model_validate(_base(proxy_method="previous_print"))
    assert _consensus().expectation_type is ExpectationType.CONSENSUS
    assert _forecast().expectation_type is ExpectationType.MODEL_FORECAST
    assert proxy.expectation_type is ExpectationType.PROXY


def test_type_cannot_be_relabelled() -> None:
    with pytest.raises(ValidationError):
        ConsensusExpectation.model_validate(_base(expectation_type="model_forecast"))
    with pytest.raises(ValidationError, match="extra"):
        ConsensusExpectation.model_validate(_base(model_id="ar1"))


def test_discriminated_parse() -> None:
    parsed = parse_expectation(
        _base(
            expectation_type="model_forecast",
            model_id="m",
            model_version="1",
            training_cutoff=datetime(2026, 10, 1, tzinfo=NY),
        )
    )
    assert isinstance(parsed, ModelForecast)
    with pytest.raises(ValidationError):
        parse_expectation(_base(expectation_type="guess"))


def test_model_forecast_requires_provenance() -> None:
    with pytest.raises(ValidationError, match="model_version"):
        ModelForecast.model_validate(
            _base(model_id="m", training_cutoff=datetime(2026, 10, 1, tzinfo=NY))
        )
    with pytest.raises(ValidationError, match="training_cutoff is after"):
        _forecast(training_cutoff=datetime(2026, 10, 10, tzinfo=NY))


def test_proxy_requires_method() -> None:
    with pytest.raises(ValidationError, match="proxy_method"):
        ProxyExpectation.model_validate(_base())


def test_creation_and_availability_required_and_ordered() -> None:
    for missing in ("forecast_created_at", "availability"):
        data = _base()
        del data[missing]
        with pytest.raises(ValidationError, match=missing):
            ConsensusExpectation.model_validate(data)
    with pytest.raises(ValidationError, match="precedes forecast_created_at"):
        _consensus(
            availability={
                "available_at": datetime(2026, 10, 9, 16, 0, tzinfo=NY),
                "precision": "provider_timestamp",
            }
        )
    with pytest.raises(ValidationError):
        _consensus(forecast_created_at=datetime(2026, 10, 9, 17, 0))


def test_market_surprise_accepts_pre_release_consensus() -> None:
    check_pre_release(_consensus(), _event(), SurpriseMode.MARKET_SURPRISE)
    check_pre_release(_consensus(), RELEASE_AT, SurpriseMode.MARKET_SURPRISE)


@pytest.mark.parametrize("delta", [timedelta(0), timedelta(minutes=1)])
def test_market_surprise_rejects_at_or_after_release(delta: timedelta) -> None:
    ts = RELEASE_AT + delta
    late = _consensus(
        forecast_created_at=ts, availability={"available_at": ts, "precision": "exact_timestamp"}
    )
    with pytest.raises(ExpectationChronologyError, match="not before the release"):
        check_pre_release(late, _event(), SurpriseMode.MARKET_SURPRISE)


def test_model_forecast_is_not_market_surprise() -> None:
    with pytest.raises(ExpectationChronologyError, match="requires a consensus"):
        check_pre_release(_forecast(), _event(), SurpriseMode.MARKET_SURPRISE)
    with pytest.raises(ExpectationChronologyError, match="requires a model_forecast"):
        check_pre_release(_consensus(), _event(), SurpriseMode.FORECAST_ERROR)
    check_pre_release(_forecast(), _event(), SurpriseMode.FORECAST_ERROR)


def test_late_actual_release_uses_actual_time() -> None:
    # Consensus published after the scheduled time but before the delayed actual release.
    ts = RELEASE_AT + timedelta(days=2)
    exp = _consensus(
        forecast_created_at=ts, availability={"available_at": ts, "precision": "exact_timestamp"}
    )
    delayed = _event(actual_release_at=RELEASE_AT + timedelta(days=9))
    check_pre_release(exp, delayed, SurpriseMode.MARKET_SURPRISE)


def test_release_mismatch_and_unreleased_rejected() -> None:
    with pytest.raises(ExpectationChronologyError, match="does not match"):
        check_pre_release(
            _consensus(release_id="CPI-2026-08"), _event(), SurpriseMode.MARKET_SURPRISE
        )
    with pytest.raises(ExpectationChronologyError, match="reference period"):
        check_pre_release(
            _consensus(reference_start=date(2026, 8, 1), reference_end=date(2026, 8, 31)),
            _event(),
            SurpriseMode.MARKET_SURPRISE,
        )
    with pytest.raises(ExpectationChronologyError, match="no actual_release_at"):
        check_pre_release(
            _consensus(), _event(actual_release_at=None), SurpriseMode.MARKET_SURPRISE
        )
    with pytest.raises(ExpectationChronologyError, match="timezone-aware"):
        check_pre_release(_consensus(), datetime(2026, 10, 15), SurpriseMode.MARKET_SURPRISE)


def test_forecast_training_cutoff_must_precede_release() -> None:
    ts = RELEASE_AT - timedelta(minutes=5)
    # Availability is valid, but a cutoff at the release instant would leak the target.
    fc = _forecast(
        forecast_created_at=RELEASE_AT,
        training_cutoff=RELEASE_AT,
        availability={"available_at": RELEASE_AT, "precision": "exact_timestamp"},
    )
    with pytest.raises(ExpectationChronologyError):
        check_pre_release(fc, RELEASE_AT, SurpriseMode.FORECAST_ERROR)
    ok = _forecast(
        forecast_created_at=ts,
        training_cutoff=ts,
        availability={"available_at": ts, "precision": "exact_timestamp"},
    )
    check_pre_release(ok, RELEASE_AT, SurpriseMode.FORECAST_ERROR)


def test_consensus_template_fixture_parses() -> None:
    with (ROOT / "examples/consensus_template.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        year, month = (int(x) for x in row["reference_period"].split("-"))
        exp = parse_expectation(
            {
                "release_id": f"{row['release_id']}-{row['reference_period']}",
                "reference_start": date(year, month, 1),
                "reference_end": date(year, month, 30),
                "expected_value": float(row["expected_value"]),
                "units": "percent_mom",
                "expectation_source": row["expectation_source"],
                "forecast_created_at": datetime.fromisoformat(row["forecast_created_at"]),
                "availability": {
                    "available_at": datetime.fromisoformat(row["available_at"]),
                    "precision": "provider_timestamp",
                },
                "source_snapshot_id": "fixture",
                "expectation_type": row["expectation_type"],
            }
        )
        assert isinstance(exp, ConsensusExpectation)
        check_pre_release(exp, RELEASE_AT, SurpriseMode.MARKET_SURPRISE)
