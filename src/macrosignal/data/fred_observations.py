"""Initial-release and revision observations from ALFRED real-time queries.

Two retrieval modes, both returning canonical :class:`MacroObservation` objects
with explicit release stage and vintage lineage:

* :func:`fetch_revision_history` - every real-time period of every reference
  date (``output_type=1`` over ``1776-07-04..9999-12-31``).  Within each
  reference date the first published value is labelled ``initial`` and every
  later vintage ``revision``.
* :func:`fetch_initial_releases` - the initial release only.  By default it is
  derived from the full history; ``server_side=True`` uses FRED's
  ``output_type=4`` and requires every record to carry its own
  ``realtime_start`` (otherwise the release date is unknown and the call fails
  rather than guessing).

Availability comes from the ALFRED vintage date, which is date-level evidence:
the stamp uses precision ``release_date_only`` / source ``alfred_vintage_date``
and is placed conservatively at the end of that day in
``America/New_York`` (``conservative_adjustment`` records the shift from the raw
date).  Task 2.11 may upgrade it to an exact release time only through a
documented calendar mapping.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from macrosignal.data.alfred import VintageDateSet, vintage_history
from macrosignal.data.fred import (
    FRED_PROVIDER,
    OUTPUT_INITIAL_RELEASE_ONLY,
    OUTPUT_OBSERVATIONS_BY_REALTIME,
    FredClient,
    FredResult,
)
from macrosignal.data.fred_metadata import SeriesMetadata
from macrosignal.data.http import ResponseSchemaError
from macrosignal.domain import (
    AvailabilityPrecision,
    AvailabilitySource,
    AvailabilityStamp,
    Frequency,
    MacroObservation,
    ReleaseStage,
)

ADAPTER_VERSION = "fred-observations-1"
ALFRED_TIMEZONE = ZoneInfo("America/New_York")
REALTIME_MIN = date(1776, 7, 4)
REALTIME_MAX = date(9999, 12, 31)
END_OF_DAY = time(23, 59, 59)


def reference_period(reference_date: date, frequency: Frequency) -> tuple[date, date]:
    """FRED observation dates are period starts; return (start, end) for ``frequency``."""
    y, m, d = reference_date.year, reference_date.month, reference_date.day
    if frequency is Frequency.DAILY:
        return reference_date, reference_date
    if frequency is Frequency.WEEKLY:
        return reference_date, reference_date + timedelta(days=6)
    if d != 1:
        raise ResponseSchemaError(
            f"{frequency.value} observation date {reference_date} is not a period start"
        )
    if frequency is Frequency.MONTHLY:
        return reference_date, date(y, m, calendar.monthrange(y, m)[1])
    if frequency is Frequency.QUARTERLY:
        if m not in (1, 4, 7, 10):
            raise ResponseSchemaError(
                f"quarterly observation date {reference_date} is not a quarter start"
            )
        return reference_date, date(y, m + 2, calendar.monthrange(y, m + 2)[1])
    if m != 1:
        raise ResponseSchemaError(f"annual observation date {reference_date} is not a year start")
    return reference_date, date(y, 12, 31)


def vintage_availability(vintage_date: date) -> AvailabilityStamp:
    """Conservative end-of-day stamp for a date-level ALFRED vintage."""
    available_at = datetime.combine(vintage_date, END_OF_DAY, tzinfo=ALFRED_TIMEZONE)
    midnight = datetime.combine(vintage_date, time(0, 0), tzinfo=ALFRED_TIMEZONE)
    return AvailabilityStamp(
        available_at=available_at,
        precision=AvailabilityPrecision.RELEASE_DATE_ONLY,
        availability_source=AvailabilitySource.ALFRED_VINTAGE_DATE,
        raw_available_date=vintage_date,
        conservative_adjustment=available_at - midnight,
    )


def _observation(
    meta: SeriesMetadata,
    *,
    reference_date: date,
    value: float,
    stage: ReleaseStage,
    realtime_start: date,
    realtime_end: date | None,
    snapshot_id: str,
    retrieved_at: datetime,
) -> MacroObservation:
    start, end = reference_period(reference_date, meta.frequency)
    return MacroObservation(
        source=FRED_PROVIDER,
        series_id=meta.series_id,
        retrieved_at=retrieved_at,
        source_snapshot_id=snapshot_id,
        adapter_version=ADAPTER_VERSION,
        release_id=None if meta.release_id is None else str(meta.release_id),
        release_stage=stage,
        reference_start=start,
        reference_end=end,
        value=value,
        units=meta.units,
        frequency=meta.frequency,
        seasonal_adjustment=meta.seasonal_adjustment,
        release_timestamp=None,
        availability=vintage_availability(realtime_start),
        vintage_date=realtime_start,
        realtime_start=realtime_start,
        realtime_end=realtime_end,
    )


def _snapshot_lookup(result: FredResult) -> dict[tuple[str, str], str]:
    ids = result.record_snapshot_ids or (result.snapshot_ids[0],) * len(result.records)
    return {
        (r["date"], r.get("realtime_start", "")): s
        for r, s in zip(result.records, ids, strict=True)
    }


def history_to_observations(
    result: FredResult,
    meta: SeriesMetadata,
    retrieved_at: datetime,
    vintages: VintageDateSet | None = None,
) -> list[MacroObservation]:
    """Label each reference date's first published value ``initial``, later ones ``revision``."""
    snaps = _snapshot_lookup(result)
    out: list[MacroObservation] = []
    for ref, chain in vintage_history(result.records, vintages).items():
        published = [v for v in chain if v.value is not None]
        for i, v in enumerate(published):
            assert v.value is not None
            out.append(
                _observation(
                    meta,
                    reference_date=ref,
                    value=v.value,
                    stage=ReleaseStage.INITIAL if i == 0 else ReleaseStage.REVISION,
                    realtime_start=v.realtime_start,
                    realtime_end=v.realtime_end,
                    snapshot_id=snaps[(ref.isoformat(), v.realtime_start.isoformat())],
                    retrieved_at=retrieved_at,
                )
            )
    return out


def fetch_revision_history(
    client: FredClient,
    meta: SeriesMetadata,
    retrieved_at: datetime,
    vintages: VintageDateSet | None = None,
    *,
    limit: int | None = None,
) -> list[MacroObservation]:
    kwargs: dict[str, Any] = {} if limit is None else {"limit": limit}
    result = client.observations(
        meta.series_id,
        realtime_start=REALTIME_MIN,
        realtime_end=REALTIME_MAX,
        output_type=OUTPUT_OBSERVATIONS_BY_REALTIME,
        **kwargs,
    )
    return history_to_observations(result, meta, retrieved_at, vintages)


def fetch_initial_releases(
    client: FredClient,
    meta: SeriesMetadata,
    retrieved_at: datetime,
    vintages: VintageDateSet | None = None,
    *,
    server_side: bool = False,
    limit: int | None = None,
) -> list[MacroObservation]:
    if not server_side:
        history = fetch_revision_history(client, meta, retrieved_at, vintages, limit=limit)
        return [o for o in history if o.release_stage is ReleaseStage.INITIAL]

    kwargs: dict[str, Any] = {} if limit is None else {"limit": limit}
    result = client.observations(
        meta.series_id,
        realtime_start=REALTIME_MIN,
        realtime_end=REALTIME_MAX,
        output_type=OUTPUT_INITIAL_RELEASE_ONLY,
        **kwargs,
    )
    snaps = result.record_snapshot_ids or (result.snapshot_ids[0],) * len(result.records)
    known = set(vintages.vintage_dates) if vintages is not None else None
    out: list[MacroObservation] = []
    for rec, snap in zip(result.records, snaps, strict=True):
        raw_start = rec.get("realtime_start")
        if not raw_start or raw_start == REALTIME_MIN.isoformat():
            raise ResponseSchemaError(
                "initial-release record has no own realtime_start; its release date is unknown"
            )
        realtime_start = date.fromisoformat(raw_start)
        if known is not None and realtime_start not in known:
            raise ResponseSchemaError(
                f"initial release date {realtime_start} is not a known vintage"
            )
        if rec.get("value") in (None, "."):
            continue
        out.append(
            _observation(
                meta,
                reference_date=date.fromisoformat(rec["date"]),
                value=float(rec["value"]),
                stage=ReleaseStage.INITIAL,
                realtime_start=realtime_start,
                realtime_end=None,
                snapshot_id=snap,
                retrieved_at=retrieved_at,
            )
        )
    return out
