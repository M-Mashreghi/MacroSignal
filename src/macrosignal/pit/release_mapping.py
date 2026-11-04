"""Versioned mapping from configured macro series to official release families.

The mapping lives in the PIT layer, independent of any source adapter: it is
built from the macro series registry plus a versioned release map
(``configs/series/release_map_v*.yaml``) and carries a ``mapping_id`` derived
from the release map version and content hash.  Availability records that use
it (Task 2.11) cite that id as their ``calendar_mapping_id``.

Ambiguity is rejected rather than resolved by guessing:

* a series claimed by several release families, or whose registry
  ``release_family`` disagrees with the family listing it, fails at build time;
* :meth:`ReleaseMappingRegistry.match_event` returns the single calendar event
  with the same family, reference period and release stage, ``None`` when there
  is none (the observation stays date-level), and raises
  :class:`AmbiguousMappingError` when several match or
  :class:`MappingConflictError` when the event date contradicts the vintage date.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from macrosignal.config.models import MacroSeriesRegistry, ReleaseMap
from macrosignal.domain import Frequency, MacroObservation, ReleaseEvent, ReleaseStage
from macrosignal.domain.manifest import stable_hash


class AmbiguousMappingError(ValueError):
    """A series or observation maps to more than one release / no unique release."""


class MappingConflictError(ValueError):
    """Calendar evidence contradicts the observation's own lineage."""


@dataclass(frozen=True)
class SeriesReleaseMapping:
    series_key: str
    series_id: str
    provider: str
    release_family: str | None
    official_source: str | None = None
    source_timezone: str | None = None
    reference_frequency: Frequency | None = None
    release_stages: tuple[ReleaseStage, ...] = ()
    max_release_lag_days: int | None = None

    @property
    def has_official_release(self) -> bool:
        return self.release_family is not None

    def canonical_stage(self, stage: ReleaseStage) -> ReleaseStage:
        """Translate a generic ``initial`` into the family's first stage (e.g. ``advance``)."""
        if stage is ReleaseStage.INITIAL and self.release_stages:
            return self.release_stages[0]
        return stage

    def reference_period_problem(
        self, reference_start: date, reference_end: date, release_date: date
    ) -> str | None:
        """Why a (reference period, release date) pair violates the family rules, or None."""
        if self.reference_frequency is Frequency.MONTHLY:
            ok = reference_start.day == 1 and reference_end.month == reference_start.month
            if not ok:
                return f"{self.release_family} publishes monthly periods"
        elif self.reference_frequency is Frequency.QUARTERLY:
            ok = reference_start.day == 1 and reference_start.month in (1, 4, 7, 10)
            if not ok:
                return f"{self.release_family} publishes quarterly periods"
        if release_date <= reference_end:
            return "release date is not after the reference period end"
        if self.max_release_lag_days is not None:
            lag = (release_date - reference_end).days
            if lag > self.max_release_lag_days:
                return (
                    f"release {lag} days after period end exceeds the "
                    f"{self.max_release_lag_days}-day bound for {self.release_family}"
                )
        return None


class ReleaseMappingRegistry:
    """Series -> release-family mapping for one release-map version."""

    def __init__(self, registry: MacroSeriesRegistry, release_map: ReleaseMap) -> None:
        self.version = release_map.version
        self.content_hash = stable_hash(release_map)
        self.mapping_id = (
            f"release_map_v{release_map.version}_{self.content_hash.removeprefix('sha256:')[:12]}"
        )
        claimed: dict[str, list[str]] = {}
        for family_name, family in release_map.release_families.items():
            for key in family.series_keys:
                claimed.setdefault(key, []).append(family_name)

        problems: list[str] = []
        mappings: dict[str, SeriesReleaseMapping] = {}
        for spec in registry.series:
            families = claimed.get(spec.key, [])
            if len(families) > 1:
                problems.append(f"series '{spec.key}' is listed by several families {families}")
                continue
            listed = families[0] if families else None
            if spec.release_family != listed:
                problems.append(
                    f"series '{spec.key}' declares release_family {spec.release_family!r} but the "
                    f"release map lists it under {listed!r}"
                )
                continue
            if listed is None:
                mappings[spec.key] = SeriesReleaseMapping(
                    series_key=spec.key,
                    series_id=spec.series_id,
                    provider=spec.provider,
                    release_family=None,
                )
                continue
            family = release_map.release_families[listed]
            mappings[spec.key] = SeriesReleaseMapping(
                series_key=spec.key,
                series_id=spec.series_id,
                provider=spec.provider,
                release_family=listed,
                official_source=family.official_source,
                source_timezone=family.source_timezone,
                reference_frequency=Frequency(family.reference_frequency)
                if family.reference_frequency
                else None,
                release_stages=tuple(ReleaseStage(s) for s in family.release_stages),
                max_release_lag_days=family.max_release_lag_days,
            )
        unknown = sorted(set(claimed) - {s.key for s in registry.series})
        if unknown:
            problems.append(f"release map lists unknown series keys {unknown}")
        by_id: dict[tuple[str, str], list[str]] = {}
        for m in mappings.values():
            by_id.setdefault((m.provider, m.series_id), []).append(m.series_key)
        for (provider, sid), keys in by_id.items():
            if len(keys) > 1:
                problems.append(f"{provider} series {sid} is configured under several keys {keys}")
        if problems:
            raise AmbiguousMappingError("; ".join(problems))
        self._by_key = mappings
        self._by_series_id = {(m.provider, m.series_id): m for m in mappings.values()}

    def for_key(self, series_key: str) -> SeriesReleaseMapping:
        try:
            return self._by_key[series_key]
        except KeyError as exc:
            raise KeyError(f"unknown series key {series_key!r}") from exc

    def for_series(self, provider: str, series_id: str) -> SeriesReleaseMapping:
        try:
            return self._by_series_id[(provider, series_id)]
        except KeyError as exc:
            raise KeyError(f"unmapped series {provider}:{series_id}") from exc

    def mappings(self) -> list[SeriesReleaseMapping]:
        return sorted(self._by_key.values(), key=lambda m: m.series_key)

    def match_event(
        self, observation: MacroObservation, events: Iterable[ReleaseEvent]
    ) -> ReleaseEvent | None:
        """The unique calendar event that published ``observation``, if provably unique."""
        mapping = self.for_series(observation.source, observation.series_id)
        if mapping.release_family is None:
            return None
        stage = mapping.canonical_stage(observation.release_stage)
        candidates = [
            e
            for e in events
            if e.release_family == mapping.release_family
            and e.reference_start == observation.reference_start
            and e.reference_end == observation.reference_end
            and e.release_stage == stage
        ]
        if not candidates:
            return None
        if len(candidates) > 1:
            raise AmbiguousMappingError(
                f"{len(candidates)} {mapping.release_family} events match "
                f"{observation.series_id} {observation.reference_start} ({stage.value})"
            )
        event = candidates[0]
        if event.actual_release_at_local is None:
            return None
        release_date = event.actual_release_at_local.date()
        if observation.vintage_date is not None and observation.vintage_date != release_date:
            raise MappingConflictError(
                f"{observation.series_id} {observation.reference_start}: vintage date "
                f"{observation.vintage_date} != {event.release_id} release date {release_date}"
            )
        problem = mapping.reference_period_problem(
            observation.reference_start, observation.reference_end, release_date
        )
        if problem:
            raise MappingConflictError(f"{event.release_id}: {problem}")
        return event
