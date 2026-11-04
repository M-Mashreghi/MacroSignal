"""Expectation provider interface (Task 3.10)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from macrosignal.domain import (
    ConsensusExpectation,
    ExpectationType,
    ModelForecast,
    ProxyExpectation,
    ReleaseEvent,
    SurpriseMode,
)
from macrosignal.surprises.expectations import (
    AmbiguousExpectationError,
    ExpectationService,
    ExpectationStatus,
    StaticExpectationProvider,
    expectation_rows,
)

NY = ZoneInfo("America/New_York")
RELEASE_AT = datetime(2026, 10, 15, 8, 30, tzinfo=NY)
EVENT = ReleaseEvent(
    release_id="CPI-2026-09",
    release_family="CPI",
    release_name="CPI",
    source="bls",
    calendar_snapshot_id="cal",
    source_timezone="America/New_York",
    scheduled_at=RELEASE_AT,
    actual_release_at=RELEASE_AT,
    reference_start=date(2026, 9, 1),
    reference_end=date(2026, 9, 30),
    release_stage="initial",
)


def _base(ts: datetime, value: float = 0.3, **kw: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "release_id": "CPI-2026-09",
        "reference_start": date(2026, 9, 1),
        "reference_end": date(2026, 9, 30),
        "expected_value": value,
        "units": "percent_mom",
        "expectation_source": "src",
        "forecast_created_at": ts,
        "availability": {"available_at": ts, "precision": "provider_timestamp"},
        "source_snapshot_id": f"snap_{ts:%m%d%H%M}",
    }
    data.update(kw)
    return data


def _consensus(ts: datetime, value: float = 0.3) -> ConsensusExpectation:
    return ConsensusExpectation.model_validate(_base(ts, value))


def _forecast(ts: datetime, value: float = 0.25) -> ModelForecast:
    return ModelForecast.model_validate(
        _base(
            ts, value, model_id="ar1", model_version="1.0", training_cutoff=ts - timedelta(hours=1)
        )
    )


def _service() -> ExpectationService:
    return ExpectationService(
        [
            StaticExpectationProvider(
                "consensus_csv",
                ExpectationType.CONSENSUS,
                [
                    _consensus(datetime(2026, 10, 9, 17, 0, tzinfo=NY), 0.3),
                    _consensus(datetime(2026, 10, 14, 17, 0, tzinfo=NY), 0.2),
                    _consensus(datetime(2026, 10, 15, 9, 0, tzinfo=NY), 0.4),  # after release
                ],
            ),
            StaticExpectationProvider(
                "ar1_baseline",
                ExpectationType.MODEL_FORECAST,
                [
                    _forecast(datetime(2026, 10, 10, 12, 0, tzinfo=NY)),
                ],
            ),
        ]
    )


def test_market_surprise_uses_latest_pre_release_consensus() -> None:
    r = _service().get(EVENT, SurpriseMode.MARKET_SURPRISE, RELEASE_AT)
    assert r.status is ExpectationStatus.AVAILABLE
    assert r.expectation_type is ExpectationType.CONSENSUS
    assert r.expectation is not None and r.expectation.expected_value == 0.2
    assert r.provider == "consensus_csv"
    assert any("not yet available" in c.reason for c in r.rejected)


def test_query_time_limits_candidates() -> None:
    r = _service().get(EVENT, SurpriseMode.MARKET_SURPRISE, datetime(2026, 10, 12, tzinfo=NY))
    assert r.expectation is not None and r.expectation.expected_value == 0.3


def test_post_release_consensus_rejected_even_when_queried_later() -> None:
    later = datetime(2026, 10, 20, tzinfo=NY)
    r = _service().get(EVENT, SurpriseMode.MARKET_SURPRISE, later)
    assert r.expectation is not None and r.expectation.expected_value == 0.2
    assert any("not before the release" in c.reason for c in r.rejected)


def test_forecast_error_mode_only_sees_model_forecasts() -> None:
    r = _service().get(EVENT, SurpriseMode.FORECAST_ERROR, RELEASE_AT)
    assert r.expectation_type is ExpectationType.MODEL_FORECAST
    assert isinstance(r.expectation, ModelForecast) and r.provider == "ar1_baseline"


def test_missing_rather_than_imputed() -> None:
    r = _service().get(EVENT, SurpriseMode.PROXY_SURPRISE, RELEASE_AT)
    assert r.status is ExpectationStatus.MISSING and r.expectation is None
    early = _service().get(EVENT, SurpriseMode.MARKET_SURPRISE, datetime(2026, 10, 1, tzinfo=NY))
    assert early.status is ExpectationStatus.MISSING


def test_provider_type_must_be_consistent() -> None:
    with pytest.raises(ValueError, match="declares consensus"):
        StaticExpectationProvider(
            "bad", ExpectationType.CONSENSUS, [_forecast(RELEASE_AT - timedelta(days=2))]
        )
    with pytest.raises(ValueError, match="unique"):
        ExpectationService(
            [
                StaticExpectationProvider("a", ExpectationType.PROXY, []),
                StaticExpectationProvider("a", ExpectationType.PROXY, []),
            ]
        )


def test_ambiguous_same_instant_values() -> None:
    ts = datetime(2026, 10, 14, 17, 0, tzinfo=NY)
    svc = ExpectationService(
        [
            StaticExpectationProvider("a", ExpectationType.CONSENSUS, [_consensus(ts, 0.2)]),
            StaticExpectationProvider("b", ExpectationType.CONSENSUS, [_consensus(ts, 0.3)]),
        ]
    )
    with pytest.raises(AmbiguousExpectationError):
        svc.get(EVENT, SurpriseMode.MARKET_SURPRISE, RELEASE_AT)


def test_rows_keep_type_and_mode_explicit() -> None:
    svc = _service()
    proxy = ProxyExpectation.model_validate(
        _base(datetime(2026, 10, 1, tzinfo=NY), 0.1, proxy_method="previous_print")
    )
    svc.providers.append(StaticExpectationProvider("prev", ExpectationType.PROXY, [proxy]))
    rows = expectation_rows([svc.get(EVENT, m, RELEASE_AT) for m in SurpriseMode])
    assert [(r["mode"], r["expectation_type"], r["status"]) for r in rows] == [
        ("market_surprise", "consensus", "available"),
        ("forecast_error", "model_forecast", "available"),
        ("proxy_surprise", "proxy", "available"),
    ]
    assert rows[1]["model_version"] == "1.0" and rows[0]["model_version"] is None
    with pytest.raises(ValueError, match="timezone-aware"):
        svc.get(EVENT, SurpriseMode.MARKET_SURPRISE, datetime(2026, 10, 15))
