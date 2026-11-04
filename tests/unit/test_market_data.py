"""Daily demo market-data provider and normalization (Task 2.14)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from macrosignal.artifacts import ArtifactKind, ArtifactRegistry
from macrosignal.data.market import (
    YAHOO_FIELD_SEMANTICS,
    RawDailyRow,
    RawMarketBatch,
    YahooDemoProvider,
    cache_raw_batch,
    normalize_daily_bars,
    rows_from_csv,
)
from macrosignal.domain import AdjustmentPolicy, LifecycleError, PriceField

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "market" / "synthetic_daily.csv"
NY = ZoneInfo("America/New_York")
RETRIEVED = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)


def _frame(path: Path = FIX) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
    df.index = df.index.tz_localize("America/New_York")
    return df


def _provider(frame: pd.DataFrame | None = None) -> YahooDemoProvider:
    df = _frame() if frame is None else frame
    return YahooDemoProvider(download=lambda a, s, e: df, clock=lambda: RETRIEVED)


def _normalized():  # type: ignore[no-untyped-def]
    p = _provider()
    batch = p.fetch_daily("SPY", date(2026, 11, 1), date(2026, 12, 1))
    return batch, normalize_daily_bars(batch, p, role="broad_us_equity")


def test_field_semantics_are_explicit() -> None:
    assert YAHOO_FIELD_SEMANTICS["Close"] == (PriceField.CLOSE, AdjustmentPolicy.SPLIT_ADJUSTED)
    assert YAHOO_FIELD_SEMANTICS["Adj Close"][1] is AdjustmentPolicy.SPLIT_AND_DIVIDEND_ADJUSTED


def test_observations_stamped_on_trading_calendar() -> None:
    _, norm = _normalized()
    closes = norm.field_series(PriceField.CLOSE)
    assert [o.timestamp for o in closes][:2] == [
        datetime(2026, 11, 20, 16, 0, tzinfo=NY),
        datetime(2026, 11, 23, 16, 0, tzinfo=NY),
    ]
    early = next(o for o in closes if o.timestamp.date() == date(2026, 11, 27))
    assert early.timestamp.hour == 13  # early close day after Thanksgiving
    opens = norm.field_series(PriceField.OPEN)
    assert opens[0].timestamp == datetime(2026, 11, 20, 9, 30, tzinfo=NY)
    adj = norm.field_series(PriceField.ADJUSTED_CLOSE)
    assert all(o.adjustment_policy is AdjustmentPolicy.SPLIT_AND_DIVIDEND_ADJUSTED for o in adj)
    assert norm.calendar == "nyse"


def test_gaps_reported_not_filled() -> None:
    _, norm = _normalized()
    assert norm.missing_sessions == (date(2026, 11, 24),)
    assert norm.missing_values == ((date(2026, 11, 27), "Volume"),)
    assert len(norm.field_series(PriceField.VOLUME)) == 4


def test_coverage_from_first_valid_row() -> None:
    _, norm = _normalized()
    asset = norm.asset
    assert asset.first_tradable_date == date(2026, 11, 20) == asset.coverage_start
    assert asset.coverage_end == date(2026, 11, 30)
    assert asset.provider == "yahoo_demo" and asset.currency == "USD"
    assert asset.timezone == "America/New_York"
    early = norm.observations[0].model_copy(
        update={"timestamp": datetime(2026, 11, 19, 16, 0, tzinfo=NY)}
    )
    with pytest.raises(LifecycleError):
        asset.check_observation(early)


def test_non_session_rows_and_duplicates_rejected() -> None:
    p = _provider()
    holiday = RawMarketBatch(
        "yahoo_demo", "SPY", (RawDailyRow(date(2026, 11, 26), {"Close": 1.0}),), b"x", RETRIEVED
    )
    with pytest.raises(ValueError, match="non-trading"):
        normalize_daily_bars(holiday, p, role="broad_us_equity")
    dup_row = RawDailyRow(date(2026, 11, 25), {"Close": 1.0})
    dup = RawMarketBatch("yahoo_demo", "SPY", (dup_row, dup_row), b"x", RETRIEVED)
    with pytest.raises(ValueError, match="duplicate"):
        normalize_daily_bars(dup, p, role="broad_us_equity")
    future = RawMarketBatch(
        "yahoo_demo", "SPY", (RawDailyRow(date(2026, 12, 2), {"Close": 1.0}),), b"x", RETRIEVED
    )
    with pytest.raises(ValueError, match="after the retrieval date"):
        normalize_daily_bars(future, p, role="broad_us_equity")


def test_missing_provider_columns_rejected() -> None:
    with pytest.raises(ValueError, match="lacks columns"):
        _provider(_frame().drop(columns=["Adj Close"])).fetch_daily(
            "SPY", date(2026, 11, 1), date(2026, 12, 1)
        )


def test_raw_payload_and_metadata_cached(tmp_path: Path) -> None:
    batch, norm = _normalized()
    reg = ArtifactRegistry(tmp_path / "data", tmp_path / "reports")
    rec = cache_raw_batch(reg, batch)
    assert rec.kind is ArtifactKind.RAW_SNAPSHOT and rec.source == "yahoo_demo"
    assert norm.snapshot_id == batch.snapshot_id == rec.artifact_id
    files = reg.read_files(rec.artifact_id)
    assert b"demo_only" in files["provider_metadata.json"]
    rows = rows_from_csv(files["payload.csv"].decode("utf-8"), list(YAHOO_FIELD_SEMANTICS))
    assert [r.day for r in rows] == [r.day for r in batch.rows]
    assert cache_raw_batch(reg, batch) == rec  # idempotent
