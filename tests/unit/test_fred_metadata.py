"""FRED series metadata normalization and definition-change flags (Task 2.3)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest

from fakes import FAKE_TIME, FakeFred, load_fred_fixture
from macrosignal.data.fred import FredClient
from macrosignal.data.fred_metadata import (
    DefinitionChangeError,
    MetadataNormalizationError,
    SeriesMetadata,
    assert_compatible,
    compare_definitions,
    fetch_series_metadata,
    normalize_series_metadata,
)
from macrosignal.data.http import ResponseSchemaError
from macrosignal.domain import Frequency, SeasonalAdjustment

Factory = Callable[..., FredClient]


def _record(**kw: Any) -> dict[str, Any]:
    rec: dict[str, Any] = dict(load_fred_fixture("series_SYNTHCPI.json")["seriess"][0])
    rec.update(kw)
    return rec


def _meta(**kw: Any) -> SeriesMetadata:
    return normalize_series_metadata(
        _record(**kw),
        {"id": 10, "name": "Consumer Price Index"},
        snapshot_ids=("raw_fred_a",),
        retrieved_at=FAKE_TIME,
    )


def test_fetch_and_normalize(fake_fred: FakeFred, fred_client_factory: Factory) -> None:
    meta = fetch_series_metadata(fred_client_factory(fake_fred), "SYNTHCPI", FAKE_TIME)
    assert meta.source == "fred_alfred"
    assert meta.frequency is Frequency.MONTHLY
    assert meta.seasonal_adjustment is SeasonalAdjustment.SEASONALLY_ADJUSTED
    assert meta.units == "Index 1982-1984=100"
    assert meta.release_id == 10 and meta.release_name == "Consumer Price Index"
    assert meta.observation_start == date(2026, 1, 1)
    assert meta.last_updated == datetime(
        2026, 10, 15, 7, 44, 2, tzinfo=timezone(timedelta(hours=-5))
    )
    assert len(meta.metadata_snapshot_ids) == 2
    assert all(s.startswith("raw_fred_") for s in meta.metadata_snapshot_ids)


@pytest.mark.parametrize(
    ("short", "long", "expected"),
    [
        ("Q", "Quarterly", Frequency.QUARTERLY),
        ("W", "Weekly, Ending Friday", Frequency.WEEKLY),
        ("D", "Daily", Frequency.DAILY),
        (None, "Annual", Frequency.ANNUAL),
    ],
)
def test_frequency_mapping(short: str | None, long: str, expected: Frequency) -> None:
    assert _meta(frequency_short=short, frequency=long).frequency is expected


@pytest.mark.parametrize(
    ("short", "expected"),
    [
        ("SAAR", SeasonalAdjustment.SEASONALLY_ADJUSTED_ANNUAL_RATE),
        ("NSA", SeasonalAdjustment.NOT_SEASONALLY_ADJUSTED),
    ],
)
def test_seasonal_mapping(short: str, expected: SeasonalAdjustment) -> None:
    assert _meta(seasonal_adjustment_short=short).seasonal_adjustment is expected


def test_unsupported_values_rejected() -> None:
    with pytest.raises(MetadataNormalizationError, match="frequency"):
        _meta(frequency_short="BW", frequency="Biweekly")
    with pytest.raises(MetadataNormalizationError, match="seasonal"):
        _meta(seasonal_adjustment_short="SSA", seasonal_adjustment="Smoothed")
    with pytest.raises(ResponseSchemaError, match="units"):
        rec = _record()
        del rec["units"]
        normalize_series_metadata(rec, None, snapshot_ids=("s",), retrieved_at=FAKE_TIME)
    with pytest.raises(ValueError):
        normalize_series_metadata(_record(), None, snapshot_ids=(), retrieved_at=FAKE_TIME)


def test_definition_change_flagged_not_merged() -> None:
    old = _meta()
    new = _meta(units="Percent Change from Year Ago", units_short="% Chg.")
    changes = compare_definitions(old, new)
    assert [(c.field, c.blocking) for c in changes] == [("units", True)]
    with pytest.raises(DefinitionChangeError, match="units"):
        assert_compatible(old, new)
    with pytest.raises(DefinitionChangeError, match="seasonal_adjustment"):
        assert_compatible(old, _meta(seasonal_adjustment_short="NSA"))
    assert old.definition_hash != new.definition_hash


def test_title_change_is_non_blocking() -> None:
    old = _meta()
    new = _meta(title="Synthetic CPI (renamed)")
    changes = assert_compatible(old, new)
    assert [(c.field, c.blocking) for c in changes] == [("title", False)]
    assert old.definition_hash == new.definition_hash


def test_compare_requires_same_series() -> None:
    with pytest.raises(ValueError, match="different series"):
        compare_definitions(_meta(), _meta(id="OTHER"))


def test_multiple_releases_rejected(fred_client_factory: Factory) -> None:
    fake = FakeFred()
    fake.single("series", "series_SYNTHCPI.json")
    fake.route("series/release", lambda p: (200, {"releases": [{"id": 1}, {"id": 2}]}))
    with pytest.raises(ResponseSchemaError, match="multiple releases"):
        fetch_series_metadata(
            fred_client_factory(fake), "SYNTHCPI", datetime(2026, 1, 1, tzinfo=UTC)
        )
