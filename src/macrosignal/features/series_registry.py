"""Macro series registry loader with release-map resolution and timing checks.

Loads the configured series registry (``configs/series/us_macro_v*.yaml``) and
release map, resolves every series to its release-family mapping, and validates
what the feature layer relies on:

* every transformation name is a known transformation, and frequency-specific
  transformations match the family's reference frequency (``mom_*`` needs a
  monthly family, ``qoq_*`` a quarterly one);
* the staleness threshold is at least one reference period long for families
  with a known frequency (otherwise a series would be stale between every pair
  of releases);
* every PIT-required series has a sufficient timing policy: an explicit
  ``timing_policy`` that agrees with its release family -
  ``release_calendar`` requires a mapped official release family, and a series
  without one must declare ``vintage_date_conservative``.

Problems are collected and raised together as :class:`SeriesRegistryError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from macrosignal.config import load_config_file
from macrosignal.config.models import MacroSeriesRegistry, MacroSeriesSpec, ReleaseMap
from macrosignal.domain import Frequency
from macrosignal.pit.release_mapping import ReleaseMappingRegistry, SeriesReleaseMapping

#: Transformation names the feature layer implements (Task 3.2).
KNOWN_TRANSFORMATIONS = frozenset(
    {"level", "level_diff", "mom_diff", "mom_pct", "yoy_pct", "qoq_annualized", "qoq_pct"}
)
_REQUIRES_FREQUENCY = {
    "mom_diff": Frequency.MONTHLY,
    "mom_pct": Frequency.MONTHLY,
    "qoq_annualized": Frequency.QUARTERLY,
    "qoq_pct": Frequency.QUARTERLY,
}
_MIN_STALENESS_DAYS = {Frequency.MONTHLY: 31, Frequency.QUARTERLY: 92}


class SeriesRegistryError(ValueError):
    """The series registry is inconsistent with the feature/timing policy."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("series registry problems:\n- " + "\n- ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class ResolvedSeries:
    spec: MacroSeriesSpec
    mapping: SeriesReleaseMapping

    @property
    def key(self) -> str:
        return self.spec.key

    @property
    def reference_frequency(self) -> Frequency | None:
        return self.mapping.reference_frequency


@dataclass(frozen=True)
class SeriesCatalog:
    registry_version: int
    release_mapping: ReleaseMappingRegistry
    series: tuple[ResolvedSeries, ...]

    def get(self, key: str) -> ResolvedSeries:
        for s in self.series:
            if s.key == key:
                return s
        raise KeyError(f"unknown series key {key!r}")

    def by_family(self, family: str) -> list[ResolvedSeries]:
        return [s for s in self.series if s.spec.family == family]

    def pit_required(self) -> list[ResolvedSeries]:
        return [s for s in self.series if s.spec.pit_required]


def _problems(spec: MacroSeriesSpec, mapping: SeriesReleaseMapping) -> list[str]:
    out: list[str] = []
    freq = mapping.reference_frequency
    for name in spec.transformation_set:
        if name not in KNOWN_TRANSFORMATIONS:
            out.append(f"{spec.key}: unknown transformation {name!r}")
            continue
        required = _REQUIRES_FREQUENCY.get(name)
        if required is not None and freq is not None and freq is not required:
            out.append(
                f"{spec.key}: transformation {name!r} needs {required.value} data but "
                f"{mapping.release_family} publishes {freq.value} periods"
            )
    if freq is not None and spec.stale_after_days < _MIN_STALENESS_DAYS.get(freq, 1):
        out.append(
            f"{spec.key}: stale_after_days={spec.stale_after_days} is shorter than one "
            f"{freq.value} period"
        )
    if spec.pit_required:
        policy = spec.timing_policy
        if policy is None:
            out.append(f"{spec.key}: PIT-required series must declare a timing_policy")
        elif policy == "release_calendar" and not mapping.has_official_release:
            out.append(
                f"{spec.key}: timing_policy 'release_calendar' requires a mapped release family"
            )
        elif policy == "vintage_date_conservative" and mapping.has_official_release:
            out.append(
                f"{spec.key}: has release family {mapping.release_family}; use "
                "timing_policy 'release_calendar'"
            )
        if spec.provider != "fred_alfred":
            out.append(f"{spec.key}: PIT-required series need a vintage-aware provider")
    return out


def build_series_catalog(registry: MacroSeriesRegistry, release_map: ReleaseMap) -> SeriesCatalog:
    mapping = ReleaseMappingRegistry(registry, release_map)
    problems: list[str] = []
    resolved: list[ResolvedSeries] = []
    for spec in registry.series:
        m = mapping.for_key(spec.key)
        problems.extend(_problems(spec, m))
        resolved.append(ResolvedSeries(spec, m))
    if problems:
        raise SeriesRegistryError(problems)
    return SeriesCatalog(registry.registry_version, mapping, tuple(resolved))


def load_series_catalog(registry_path: Path | str, release_map_path: Path | str) -> SeriesCatalog:
    return build_series_catalog(
        load_config_file(registry_path, MacroSeriesRegistry),
        load_config_file(release_map_path, ReleaseMap),
    )
