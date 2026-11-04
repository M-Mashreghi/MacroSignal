"""Inflation feature pipeline: headline/core CPI and PCE level and momentum.

Thin, explicit wrapper over :func:`build_family_features` for the ``inflation``
family of the series registry (CPI and PCE release families).  Features are
computed only from vintages available at the decision time, and every
:class:`~macrosignal.features.as_of_features.AsOfFeature` carries its age and
staleness.
"""

from __future__ import annotations

from datetime import datetime

from macrosignal.features.as_of_features import FeatureSet, build_family_features
from macrosignal.features.series_registry import SeriesCatalog
from macrosignal.pit.as_of import PitStore

INFLATION_FAMILY = "inflation"
INFLATION_RELEASE_FAMILIES = frozenset({"CPI", "PCE"})


def build_inflation_features(
    store: PitStore, catalog: SeriesCatalog, as_of: datetime
) -> FeatureSet:
    for s in catalog.by_family(INFLATION_FAMILY):
        if s.mapping.release_family not in INFLATION_RELEASE_FAMILIES:
            raise ValueError(
                f"inflation series {s.key} maps to {s.mapping.release_family}, expected one of "
                f"{sorted(INFLATION_RELEASE_FAMILIES)}"
            )
    return build_family_features(store, catalog, INFLATION_FAMILY, as_of)
