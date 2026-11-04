"""Growth / activity feature pipeline with GDP estimate-stage awareness.

GDP (quarterly, ``GDP`` release family) and activity series such as industrial
production are built from the as-of view, so at each decision time the GDP
value is the estimate round (advance / second / third / revision) that was
public then; every feature keeps its reference period and release stage.

A later estimate must never rewrite an earlier decision.  The as-of engine
guarantees that recomputing a past decision time yields the same features, and
:class:`FeatureDecisionLog` makes it enforceable: it records the feature
set used at each decision time with a content hash and refuses to record a
different feature set for a time already decided.
"""

from __future__ import annotations

from datetime import datetime

from macrosignal.domain.manifest import stable_hash
from macrosignal.features.as_of_features import FeatureSet, build_family_features
from macrosignal.features.series_registry import SeriesCatalog
from macrosignal.pit.as_of import PitStore

GROWTH_FAMILY = "growth"


def build_growth_features(store: PitStore, catalog: SeriesCatalog, as_of: datetime) -> FeatureSet:
    for s in catalog.by_family(GROWTH_FAMILY):
        if s.spec.series_id == "GDPC1" and s.mapping.release_family != "GDP":
            raise ValueError("real GDP must map to the GDP release family (estimate stages)")
    return build_family_features(store, catalog, GROWTH_FAMILY, as_of)


class DecisionOverwriteError(RuntimeError):
    """Attempt to replace the features already used for a past decision."""


class FeatureDecisionLog:
    """Append-only record of the feature sets used at each decision time."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, datetime], tuple[str, FeatureSet]] = {}

    @staticmethod
    def fingerprint(features: FeatureSet) -> str:
        return stable_hash(features.model_dump(mode="python"))

    def record(self, features: FeatureSet) -> str:
        key = (features.family, features.as_of)
        digest = self.fingerprint(features)
        existing = self._entries.get(key)
        if existing is not None:
            if existing[0] != digest:
                raise DecisionOverwriteError(
                    f"{features.family} features for {features.as_of.isoformat()} were already "
                    "decided with different values; later estimates cannot rewrite them"
                )
            return digest
        self._entries[key] = (digest, features)
        return digest

    def get(self, family: str, as_of: datetime) -> FeatureSet:
        return self._entries[(family, as_of)][1]

    def __len__(self) -> int:
        return len(self._entries)
