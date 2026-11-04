"""Cross-asset universe and as-of tradability resolver.

Combines the configured universe (``configs/assets/*.yaml``) with per-asset
:class:`~macrosignal.domain.AssetMetadata` (provider coverage and lifecycle,
e.g. from the market-data adapter) and answers, for any execution date, which
assets are tradable.  An asset is tradable on ``d`` only if it has metadata,
``d`` is within its tradable lifecycle *and* within provider coverage; an ETF
proxy is therefore never used before its inception or first valid provider row.
Each exclusion carries a reason, so gaps in the universe are visible.

Lifecycle policy ``provider_first_valid`` (the v1 config) requires the
metadata's coverage start to be the first tradable date it reports (no
coverage claimed before the instrument's first valid data).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from macrosignal.config.models import AssetUniverse
from macrosignal.domain import AssetMetadata

SUPPORTED_LIFECYCLE_POLICIES = frozenset({"provider_first_valid"})


class ExclusionReason(StrEnum):
    NO_METADATA = "no_metadata"
    BEFORE_INCEPTION = "before_inception"
    AFTER_LAST_TRADABLE = "after_last_tradable"
    OUTSIDE_COVERAGE = "outside_coverage"


class TradableUniverse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: date
    assets: tuple[str, ...]
    excluded: dict[str, ExclusionReason]


class UniverseError(ValueError):
    """Configured universe and asset metadata are inconsistent."""


class UniverseResolver:
    def __init__(self, config: AssetUniverse, metadata: Mapping[str, AssetMetadata]) -> None:
        problems: list[str] = []
        self.roles = {a.id: a.role for a in config.assets}
        for spec in config.assets:
            if spec.lifecycle_policy not in SUPPORTED_LIFECYCLE_POLICIES:
                problems.append(f"{spec.id}: unsupported lifecycle policy {spec.lifecycle_policy}")
            meta = metadata.get(spec.id)
            if meta is None:
                continue
            if meta.asset_id != spec.id:
                problems.append(f"metadata for {spec.id} describes {meta.asset_id}")
            if meta.role != spec.role:
                problems.append(f"{spec.id}: metadata role {meta.role} != configured {spec.role}")
            if (
                spec.lifecycle_policy == "provider_first_valid"
                and meta.coverage_start != meta.first_tradable_date
            ):
                problems.append(
                    f"{spec.id}: provider_first_valid requires "
                    "coverage_start == first_tradable_date"
                )
        unknown = sorted(set(metadata) - set(self.roles))
        if unknown:
            problems.append(f"metadata for unconfigured assets {unknown}")
        if problems:
            raise UniverseError("; ".join(problems))
        self.asset_ids = tuple(a.id for a in config.assets)
        self.metadata = dict(metadata)

    def reason(self, asset_id: str, day: date) -> ExclusionReason | None:
        meta = self.metadata.get(asset_id)
        if meta is None:
            return ExclusionReason.NO_METADATA
        if day < meta.first_tradable_date:
            return ExclusionReason.BEFORE_INCEPTION
        if meta.last_tradable_date is not None and day > meta.last_tradable_date:
            return ExclusionReason.AFTER_LAST_TRADABLE
        if not meta.is_covered_on(day):
            return ExclusionReason.OUTSIDE_COVERAGE
        return None

    def tradable_on(self, day: date) -> TradableUniverse:
        excluded: dict[str, ExclusionReason] = {}
        tradable: list[str] = []
        for asset_id in self.asset_ids:
            r = self.reason(asset_id, day)
            if r is None:
                tradable.append(asset_id)
            else:
                excluded[asset_id] = r
        return TradableUniverse(date=day, assets=tuple(tradable), excluded=excluded)

    def universe_series(self, days: Iterable[date]) -> list[TradableUniverse]:
        return [self.tradable_on(d) for d in days]
