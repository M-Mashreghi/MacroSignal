"""Event clusters, overlap / contamination and the statistical event study.

**Clusters.**  Events whose reacting sessions lie within ``max_session_gap``
trading sessions of each other form a cluster (chained).  A cluster with more
than one event is *contaminated*: its returns mix several releases (e.g. CPI
and retail sales on the same morning), so each member is flagged.

**Grouping.**  :func:`event_study` groups event responses by any of release
family, surprise bucket and regime.  Surprise buckets come from declared
z-score thresholds (``negative`` / ``neutral`` / ``positive``, or ``missing``
when no surprise exists - never imputed).  Contaminated events are excluded by
default (and counted).  Each group reports the sample size, mean, median,
standard deviation and a percentile bootstrap confidence interval of the mean
with a fixed seed; groups below ``min_sample`` carry a ``small_sample`` warning
and no confidence interval.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.event_study.alignment import EventMarketAlignment


class EventCluster(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cluster_id: str
    release_ids: tuple[str, ...]
    families: tuple[str, ...]
    first_session: date
    last_session: date

    @property
    def contaminated(self) -> bool:
        return len(self.release_ids) > 1


def _sessions_between(cal: UsTradingCalendar, a: date, b: date) -> int:
    return len(cal.sessions(a, b)) - 1 if b >= a else -1


def detect_clusters(
    alignments: Sequence[EventMarketAlignment],
    calendar: UsTradingCalendar,
    *,
    max_session_gap: int = 0,
) -> list[EventCluster]:
    ordered = sorted(alignments, key=lambda a: (a.reaction_session, a.event_time))
    clusters: list[list[EventMarketAlignment]] = []
    for a in ordered:
        if clusters:
            last = clusters[-1][-1]
            if (
                _sessions_between(calendar, last.reaction_session, a.reaction_session)
                <= max_session_gap
            ):
                clusters[-1].append(a)
                continue
        clusters.append([a])
    out = []
    for members in clusters:
        first = members[0].reaction_session
        out.append(
            EventCluster(
                cluster_id=f"cluster_{first.isoformat()}_{len(members)}",
                release_ids=tuple(m.release_id for m in members),
                families=tuple(sorted({m.release_family for m in members})),
                first_session=first,
                last_session=members[-1].reaction_session,
            )
        )
    return out


def contamination_map(clusters: Sequence[EventCluster]) -> dict[str, bool]:
    return {rid: c.contaminated for c in clusters for rid in c.release_ids}


class SurpriseBuckets(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    negative_below: float = -0.5
    positive_above: float = 0.5

    def bucket(self, z: float | None) -> str:
        if z is None:
            return "missing"
        if z < self.negative_below:
            return "negative"
        if z > self.positive_above:
            return "positive"
        return "neutral"


class EventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    release_family: str
    window_return: float
    surprise_z: float | None = None
    regime: str | None = None
    contaminated: bool = False


class GroupStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: dict[str, str]
    n: int
    n_contaminated_excluded: int
    mean: float | None
    median: float | None
    std: float | None
    ci_low: float | None
    ci_high: float | None
    ci_level: float
    small_sample: bool


class EventStudySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group_by: tuple[str, ...] = ("release_family", "surprise_bucket")
    buckets: SurpriseBuckets = SurpriseBuckets()
    min_sample: int = Field(default=10, ge=2)
    n_bootstrap: int = Field(default=2000, ge=100)
    ci_level: float = Field(default=0.95, gt=0, lt=1)
    seed: int = 0
    exclude_contaminated: bool = True


_ALLOWED_KEYS = frozenset({"release_family", "surprise_bucket", "regime"})


def _key(r: EventResponse, fields: Sequence[str], buckets: SurpriseBuckets) -> tuple[str, ...]:
    values = {
        "release_family": r.release_family,
        "surprise_bucket": buckets.bucket(r.surprise_z),
        "regime": r.regime or "unknown",
    }
    return tuple(values[f] for f in fields)


def event_study(
    responses: Sequence[EventResponse], settings: EventStudySettings | None = None
) -> list[GroupStatistics]:
    s = settings or EventStudySettings()
    bad = [g for g in s.group_by if g not in _ALLOWED_KEYS]
    if bad:
        raise ValueError(f"unsupported grouping keys {bad}")
    groups: dict[tuple[str, ...], list[EventResponse]] = defaultdict(list)
    for r in responses:
        groups[_key(r, s.group_by, s.buckets)].append(r)
    rng = np.random.default_rng(s.seed)
    out: list[GroupStatistics] = []
    for key in sorted(groups):
        members = groups[key]
        kept = [m for m in members if not (s.exclude_contaminated and m.contaminated)]
        excluded = len(members) - len(kept)
        x = np.array([m.window_return for m in kept], dtype=float)
        n = len(x)
        small = n < s.min_sample
        lo = hi = None
        if n and not small:
            boots = rng.choice(x, size=(s.n_bootstrap, n), replace=True).mean(axis=1)
            alpha = (1 - s.ci_level) / 2
            lo, hi = (float(v) for v in np.quantile(boots, [alpha, 1 - alpha]))
        out.append(
            GroupStatistics(
                key=dict(zip(s.group_by, key, strict=True)),
                n=n,
                n_contaminated_excluded=excluded,
                mean=float(x.mean()) if n else None,
                median=float(np.median(x)) if n else None,
                std=float(x.std(ddof=1)) if n > 1 else None,
                ci_low=lo,
                ci_high=hi,
                ci_level=s.ci_level,
                small_sample=small,
            )
        )
    return out
