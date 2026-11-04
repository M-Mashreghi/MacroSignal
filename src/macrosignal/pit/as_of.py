"""Point-in-time as-of query engine.

:class:`PitStore` holds every vintage / release stage of every observation
(normally the output of the availability resolver) and answers
``as_of(t)``: for each ``(source, series_id, reference period)`` it returns the
observation with the greatest ``available_at <= t`` - i.e. exactly what was
knowable at ``t``, never a later revision.

Ties at the same availability instant are broken by release-stage order and
then real-time start, and are otherwise rejected as ambiguous.  An optional
``min_precision`` excludes observations whose availability precision is not
good enough for an experiment (they are *excluded*, not replaced by an older
vintage).  :func:`assert_no_lookahead` is the blocking golden-rule check for any
set of inputs used at a decision time.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from macrosignal.domain import AvailabilityPrecision, MacroObservation, ReleaseStage
from macrosignal.pit.availability_resolver import ResolvedObservation, meets_precision

SeriesKey = tuple[str, str]  # (source, series_id)
ObservationKey = tuple[str, str, date]  # (source, series_id, reference_start)

STAGE_ORDER: dict[ReleaseStage, int] = {
    ReleaseStage.INITIAL: 0,
    ReleaseStage.ADVANCE: 0,
    ReleaseStage.SECOND: 1,
    ReleaseStage.THIRD: 2,
    ReleaseStage.REVISION: 3,
    ReleaseStage.BENCHMARK_REVISION: 4,
}


class LookaheadError(RuntimeError):
    """An input was not available at the decision time (blocks the run)."""


class AmbiguousVintageError(ValueError):
    """Two different values became available at the same instant for one observation."""


def _require_aware(t: datetime) -> None:
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("as-of timestamps must be timezone-aware")


def _rank(obs: MacroObservation) -> tuple[datetime, int, date]:
    return (
        obs.availability.available_at,
        STAGE_ORDER[obs.release_stage],
        obs.realtime_start or date.min,
    )


@dataclass(frozen=True)
class AsOfResult:
    as_of: datetime
    observations: dict[ObservationKey, MacroObservation]
    excluded_for_precision: tuple[ObservationKey, ...] = ()

    def series(self, source: str, series_id: str) -> list[MacroObservation]:
        """Known observations of one series ordered by reference period."""
        rows = [
            o for (s, sid, _), o in self.observations.items() if (s, sid) == (source, series_id)
        ]
        return sorted(rows, key=lambda o: o.reference_start)

    def latest(self, source: str, series_id: str) -> MacroObservation | None:
        rows = self.series(source, series_id)
        return rows[-1] if rows else None

    @property
    def max_available_at(self) -> datetime | None:
        if not self.observations:
            return None
        return max(o.availability.available_at for o in self.observations.values())


class PitStore:
    """In-memory store of all vintages with as-of reconstruction."""

    def __init__(self, observations: Iterable[MacroObservation | ResolvedObservation] = ()) -> None:
        self._by_key: dict[ObservationKey, list[MacroObservation]] = {}
        self.add(observations)

    def add(self, observations: Iterable[MacroObservation | ResolvedObservation]) -> None:
        for item in observations:
            obs = item.observation if isinstance(item, ResolvedObservation) else item
            key = (obs.source, obs.series_id, obs.reference_start)
            bucket = self._by_key.setdefault(key, [])
            if obs not in bucket:
                bucket.append(obs)
                bucket.sort(key=_rank)

    def __len__(self) -> int:
        return sum(len(v) for v in self._by_key.values())

    def vintages(
        self, source: str, series_id: str, reference_start: date
    ) -> list[MacroObservation]:
        """Full chronological vintage chain of one observation."""
        return list(self._by_key.get((source, series_id, reference_start), []))

    def as_of(
        self,
        t: datetime,
        *,
        series: Iterable[SeriesKey] | None = None,
        min_precision: AvailabilityPrecision | None = None,
    ) -> AsOfResult:
        _require_aware(t)
        wanted = set(series) if series is not None else None
        chosen: dict[ObservationKey, MacroObservation] = {}
        excluded: list[ObservationKey] = []
        for key, chain in self._by_key.items():
            if wanted is not None and (key[0], key[1]) not in wanted:
                continue
            known = [o for o in chain if o.availability.available_at <= t]
            if not known:
                continue
            best = known[-1]
            top = [o for o in known if _rank(o) == _rank(best)]
            if len({o.value for o in top}) > 1:
                raise AmbiguousVintageError(
                    f"{key}: several values became available at "
                    f"{best.availability.available_at.isoformat()}"
                )
            if min_precision is not None and not meets_precision(
                best.availability.precision, min_precision
            ):
                excluded.append(key)
                continue
            chosen[key] = best
        assert_no_lookahead(chosen.values(), t)
        return AsOfResult(
            as_of=t, observations=chosen, excluded_for_precision=tuple(sorted(excluded))
        )


def assert_no_lookahead(observations: Iterable[MacroObservation], decision_time: datetime) -> None:
    """Raise :class:`LookaheadError` unless ``max(available_at) <= decision_time``."""
    _require_aware(decision_time)
    for obs in observations:
        if obs.availability.available_at > decision_time:
            raise LookaheadError(
                f"{obs.source}:{obs.series_id} {obs.reference_start} "
                f"({obs.release_stage.value}) available at "
                f"{obs.availability.available_at.isoformat()} > {decision_time.isoformat()}"
            )
