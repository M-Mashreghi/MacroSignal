"""Cross-asset universe & tradability resolver (Task 5.1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from macrosignal.config import load_config_file
from macrosignal.config.models import AssetUniverse
from macrosignal.domain import AssetMetadata
from macrosignal.portfolio.universe import ExclusionReason, UniverseError, UniverseResolver

ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_config_file(ROOT / "configs/assets/cross_asset_v1.yaml", AssetUniverse)
ROLES = {a.id: a.role for a in CONFIG.assets}


def _meta(asset: str, first: date, last: date | None = None, **kw: Any) -> AssetMetadata:
    data: dict[str, Any] = {
        "asset_id": asset,
        "role": ROLES[asset],
        "provider": "SYNTHETIC",
        "currency": "USD",
        "timezone": "America/New_York",
        "first_tradable_date": first,
        "coverage_start": first,
        "last_tradable_date": last,
        "price_adjustment_policy": "split_and_dividend_adjusted",
        "return_convention": "adjusted_close_to_adjusted_close",
    }
    data.update(kw)
    return AssetMetadata.model_validate(data)


# Synthetic inception dates (not real listing dates).
META = {
    "SPY": _meta("SPY", date(2000, 1, 3)),
    "TLT": _meta("TLT", date(2002, 7, 30)),
    "GLD": _meta("GLD", date(2004, 11, 18)),
    "USO": _meta("USO", date(2006, 4, 10), last=date(2026, 6, 30)),
}


def test_tradable_universe_respects_inception() -> None:
    r = UniverseResolver(CONFIG, META)
    u = r.tradable_on(date(2003, 1, 2))
    assert u.assets == ("SPY", "TLT")
    assert u.excluded["GLD"] is ExclusionReason.BEFORE_INCEPTION
    assert u.excluded["QQQ"] is ExclusionReason.NO_METADATA
    later = r.tradable_on(date(2010, 6, 1))
    assert set(later.assets) == {"SPY", "TLT", "GLD", "USO"}
    after = r.tradable_on(date(2026, 7, 1))
    assert after.excluded["USO"] is ExclusionReason.AFTER_LAST_TRADABLE


def test_coverage_end_excludes() -> None:
    meta = {**META, "SPY": _meta("SPY", date(2000, 1, 3), coverage_end=date(2020, 1, 1))}
    u = UniverseResolver(CONFIG, meta).tradable_on(date(2021, 1, 4))
    assert u.excluded["SPY"] is ExclusionReason.OUTSIDE_COVERAGE


def test_series_is_point_in_time_per_date() -> None:
    days = [date(2004, 11, 17), date(2004, 11, 18)]
    series = UniverseResolver(CONFIG, META).universe_series(days)
    assert "GLD" not in series[0].assets and "GLD" in series[1].assets


@pytest.mark.parametrize(
    ("meta", "match"),
    [
        ({"SPY": _meta("SPY", date(2000, 1, 3), role="gold_proxy")}, "role"),
        (
            {"SPY": _meta("SPY", date(2000, 1, 3), coverage_start=date(2001, 1, 2))},
            "provider_first_valid",
        ),
        (
            {
                "XYZ": AssetMetadata.model_validate(
                    {**_meta("SPY", date(2000, 1, 3)).model_dump(), "asset_id": "XYZ"}
                )
            },
            "unconfigured",
        ),
    ],
)
def test_inconsistent_metadata_rejected(meta: dict[str, AssetMetadata], match: str) -> None:
    with pytest.raises(UniverseError, match=match):
        UniverseResolver(CONFIG, meta)
