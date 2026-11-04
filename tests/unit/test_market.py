"""MarketObservation and AssetMetadata lifecycle contract (Task 1.7)."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from macrosignal.domain import (
    AdjustmentPolicy,
    AssetMetadata,
    LifecycleError,
    MarketObservation,
    PriceField,
)

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")


def _asset(**kw: Any) -> AssetMetadata:
    data: dict[str, Any] = {
        "asset_id": "SPY",
        "role": "broad_us_equity",
        "provider": "SYNTHETIC",
        "currency": "USD",
        "timezone": "America/New_York",
        "first_tradable_date": date(1993, 1, 29),
        "coverage_start": date(2000, 1, 3),
        "price_adjustment_policy": "split_and_dividend_adjusted",
        "return_convention": "adjusted_close_to_adjusted_close",
    }
    data.update(kw)
    return AssetMetadata.model_validate(data)


def _obs(**kw: Any) -> MarketObservation:
    data: dict[str, Any] = {
        "asset_id": "SPY",
        "timestamp": datetime(2026, 10, 15, 16, 0, tzinfo=NY),
        "field": "adjusted_close",
        "value": 604.0,
        "currency": "USD",
        "provider": "SYNTHETIC",
        "adjustment_policy": "split_and_dividend_adjusted",
        "retrieved_at": datetime(2026, 10, 16, 1, 0, tzinfo=UTC),
        "snapshot_id": "snap_mkt_001",
    }
    data.update(kw)
    return MarketObservation.model_validate(data)


def test_valid_asset_and_observation() -> None:
    asset = _asset()
    obs = _obs()
    asset.check_observation(obs)
    assert obs.field is PriceField.ADJUSTED_CLOSE
    assert asset.price_adjustment_policy is AdjustmentPolicy.SPLIT_AND_DIVIDEND_ADJUSTED


def test_coverage_before_inception_rejected() -> None:
    with pytest.raises(ValidationError, match="backfill before inception"):
        _asset(coverage_start=date(1990, 1, 2))


@pytest.mark.parametrize(
    ("kw", "match"),
    [
        ({"last_tradable_date": date(1990, 1, 1)}, "last_tradable_date is before"),
        (
            {"coverage_end": date(1999, 1, 1)},
            "coverage_end is before coverage_start",
        ),
        (
            {"last_tradable_date": date(2010, 1, 1), "coverage_end": date(2011, 1, 1)},
            "coverage_end is after last_tradable_date",
        ),
    ],
)
def test_lifecycle_ordering(kw: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _asset(**kw)


def test_observation_before_inception_or_coverage_rejected() -> None:
    asset = _asset()
    with pytest.raises(LifecycleError, match="tradable lifecycle"):
        asset.check_observation(
            _obs(
                timestamp=datetime(1992, 6, 1, 16, tzinfo=NY),
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    with pytest.raises(LifecycleError, match="provider coverage"):
        asset.check_observation(
            _obs(
                timestamp=datetime(1999, 6, 1, 16, tzinfo=NY),
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )


def test_observation_after_delisting_rejected() -> None:
    asset = _asset(last_tradable_date=date(2026, 10, 14))
    with pytest.raises(LifecycleError, match="tradable lifecycle"):
        asset.check_observation(_obs())


def test_lifecycle_uses_exchange_local_date() -> None:
    asset = _asset(first_tradable_date=date(2026, 10, 15), coverage_start=date(2026, 10, 15))
    # 2026-10-15 02:00 UTC is still 2026-10-14 in New York: before inception.
    with pytest.raises(LifecycleError, match="tradable lifecycle"):
        asset.check_observation(
            _obs(
                timestamp=datetime(2026, 10, 15, 2, 0, tzinfo=UTC),
                field="close",
                adjustment_policy="unadjusted",
            )
        )


def test_provider_and_currency_mismatch_rejected() -> None:
    asset = _asset()
    with pytest.raises(LifecycleError, match="provider"):
        asset.check_observation(_obs(provider="OTHER"))
    with pytest.raises(LifecycleError, match="currency"):
        asset.check_observation(_obs(currency="EUR"))


def test_explicit_metadata_required() -> None:
    for missing in ("provider", "timezone", "currency", "price_adjustment_policy"):
        data = _asset().model_dump()
        del data[missing]
        with pytest.raises(ValidationError, match=missing):
            AssetMetadata.model_validate(data)
    with pytest.raises(ValidationError, match="timezone"):
        _asset(timezone="Etc/GMT+5")
    with pytest.raises(ValidationError, match="currency"):
        _asset(currency="usd")


def test_observation_value_and_adjustment_checks() -> None:
    with pytest.raises(ValidationError, match="positive"):
        _obs(value=0.0)
    with pytest.raises(ValidationError, match="cannot carry adjustment"):
        _obs(adjustment_policy="unadjusted")
    with pytest.raises(ValidationError, match="cannot carry adjustment"):
        _obs(field="close", adjustment_policy="split_and_dividend_adjusted")
    with pytest.raises(ValidationError, match="retrieved_at"):
        _obs(retrieved_at=datetime(2026, 10, 15, 15, 0, tzinfo=NY))
    with pytest.raises(ValidationError):
        _obs(timestamp=datetime(2026, 10, 15, 16, 0))
    assert _obs(field="volume", value=0.0, adjustment_policy="unadjusted").value == 0.0


def test_market_price_fixture_parses() -> None:
    asset = _asset()
    with (ROOT / "examples/market_price_fixture.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    for row in rows:
        ts = datetime.fromisoformat(row["timestamp"])
        for field, policy in (
            ("open", "unadjusted"),
            ("close", "unadjusted"),
            ("adjusted_close", "split_and_dividend_adjusted"),
        ):
            obs = _obs(
                asset_id=row["asset_id"],
                timestamp=ts,
                field=field,
                value=float(row[field]),
                provider=row["provider"],
                adjustment_policy=policy,
                retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
            )
            asset.check_observation(obs)
