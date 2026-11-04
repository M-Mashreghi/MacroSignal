"""Policy / rates feature pipeline.

Three explicitly separated parts, each with its own availability timing:

* **policy-rate features** - configured ``policy`` family series (e.g. the
  effective federal funds rate) through the as-of feature engine;
* **rates state** - selected Treasury curve tenors from the latest curve
  *knowable* at ``t``.  Curves are stamped at end of their observation day, so a
  morning decision on a macro-release day still sees the previous day's curve
  while macro features may already reflect the 08:30 release;
* **FOMC event markers** - time since the last *actually released* statement
  and until the next *scheduled* one (schedules are published in advance; the
  calendar snapshot id is carried for audit).  No policy surprise is computed
  here: that requires a valid pre-meeting expectation (Task 2.9).

The rates staleness threshold is a required argument so it comes from the
caller's configuration rather than a hidden default.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict, FiniteFloat

from macrosignal.calendar.fomc import FomcMeeting
from macrosignal.data.treasury import YieldCurveBatch
from macrosignal.domain import AvailabilityPrecision
from macrosignal.features.as_of_features import FeatureSet, build_family_features
from macrosignal.features.series_registry import SeriesCatalog
from macrosignal.pit.as_of import PitStore

POLICY_FAMILY = "policy"
DEFAULT_TENORS = ("3M", "2Y", "10Y")


class RateFeature(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_name: str
    curve: str
    tenor: str
    as_of: AwareDatetime
    value: FiniteFloat
    observation_date: date
    available_at: AwareDatetime
    availability_precision: AvailabilityPrecision
    age_since_available: timedelta
    stale_after_days: int
    stale: bool
    snapshot_id: str


class FomcMarker(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    last_statement_id: str | None
    last_statement_at: AwareDatetime | None
    days_since_last_statement: float | None
    next_meeting_id: str | None
    next_scheduled_at: AwareDatetime | None
    days_to_next_statement: float | None
    statement_released_today: bool
    calendar_snapshot_id: str | None


class PolicyRatesFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    policy: FeatureSet
    rates: dict[str, RateFeature]
    missing_rates: tuple[str, ...]
    fomc: FomcMarker


def rate_features(
    curves: Iterable[YieldCurveBatch],
    as_of: datetime,
    *,
    tenors: Sequence[str] = DEFAULT_TENORS,
    stale_after_days: int,
) -> tuple[dict[str, RateFeature], list[str]]:
    out: dict[str, RateFeature] = {}
    missing: list[str] = []
    for batch in curves:
        usable = batch.available_at(as_of)
        for tenor in tenors:
            name = f"{batch.curve.value}_{tenor.lower()}"
            points = [p for p in usable if p.tenor == tenor]
            if not points:
                missing.append(name)
                continue
            p = max(points, key=lambda x: x.observation_date)
            age = as_of - p.availability.available_at
            out[name] = RateFeature(
                feature_name=name,
                curve=batch.curve.value,
                tenor=tenor,
                as_of=as_of,
                value=p.yield_pct,
                observation_date=p.observation_date,
                available_at=p.availability.available_at,
                availability_precision=p.availability.precision,
                age_since_available=age,
                stale_after_days=stale_after_days,
                stale=age > timedelta(days=stale_after_days),
                snapshot_id=p.snapshot_id,
            )
    return out, missing


def fomc_marker(meetings: Sequence[FomcMeeting], as_of: datetime) -> FomcMarker:
    released = [
        m
        for m in meetings
        if m.statement.actual_release_at is not None and m.statement.actual_release_at <= as_of
    ]
    last = max(released, key=lambda m: m.statement.actual_release_at or as_of, default=None)
    upcoming = [m for m in meetings if m.statement.scheduled_at > as_of and m not in released]
    nxt = min(upcoming, key=lambda m: m.statement.scheduled_at, default=None)
    last_at = last.statement.actual_release_at if last else None
    local_day = as_of.astimezone(meetings[0].statement.zone).date() if meetings else None
    return FomcMarker(
        as_of=as_of,
        last_statement_id=last.meeting_id if last else None,
        last_statement_at=last_at,
        days_since_last_statement=(as_of - last_at).total_seconds() / 86400 if last_at else None,
        next_meeting_id=nxt.meeting_id if nxt else None,
        next_scheduled_at=nxt.statement.scheduled_at if nxt else None,
        days_to_next_statement=(nxt.statement.scheduled_at - as_of).total_seconds() / 86400
        if nxt
        else None,
        statement_released_today=bool(
            last_at is not None
            and local_day is not None
            and last_at.astimezone(last.statement.zone).date() == local_day  # type: ignore[union-attr]
        ),
        calendar_snapshot_id=meetings[0].statement.calendar_snapshot_id if meetings else None,
    )


def build_policy_rates_features(
    store: PitStore,
    catalog: SeriesCatalog,
    as_of: datetime,
    *,
    curves: Iterable[YieldCurveBatch],
    meetings: Sequence[FomcMeeting],
    rates_stale_after_days: int,
    tenors: Sequence[str] = DEFAULT_TENORS,
) -> PolicyRatesFeatures:
    policy = build_family_features(store, catalog, POLICY_FAMILY, as_of)
    rates, missing = rate_features(
        curves, as_of, tenors=tenors, stale_after_days=rates_stale_after_days
    )
    return PolicyRatesFeatures(
        as_of=as_of,
        policy=policy,
        rates=rates,
        missing_rates=tuple(sorted(missing)),
        fomc=fomc_marker(meetings, as_of),
    )
