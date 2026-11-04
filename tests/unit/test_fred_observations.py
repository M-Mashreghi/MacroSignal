"""Initial-release vs revision observation retrieval (Task 2.5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from fakes import FAKE_TIME, FakeFred
from macrosignal.data.alfred import fetch_vintage_dates
from macrosignal.data.fred import FredClient
from macrosignal.data.fred_metadata import fetch_series_metadata
from macrosignal.data.fred_observations import (
    fetch_initial_releases,
    fetch_revision_history,
    reference_period,
    vintage_availability,
)
from macrosignal.data.http import ResponseSchemaError
from macrosignal.domain import AvailabilityPrecision, Frequency, ReleaseStage

NY = ZoneInfo("America/New_York")
Factory = Callable[..., FredClient]


def _setup(fake: FakeFred, factory: Factory):  # type: ignore[no-untyped-def]
    client = factory(fake)
    meta = fetch_series_metadata(client, "SYNTHCPI", FAKE_TIME)
    vintages = fetch_vintage_dates(client, "SYNTHCPI", FAKE_TIME)
    return client, meta, vintages


def test_revision_history_labels_stages(fake_fred: FakeFred, fred_client_factory: Factory) -> None:
    client, meta, vintages = _setup(fake_fred, fred_client_factory)
    obs = fetch_revision_history(client, meta, FAKE_TIME, vintages, limit=2)
    aug = [o for o in obs if o.reference_start == date(2026, 8, 1)]
    assert [(o.release_stage, o.value) for o in aug] == [
        (ReleaseStage.INITIAL, 100.0),
        (ReleaseStage.REVISION, 100.2),
    ]
    assert aug[0].reference_end == date(2026, 8, 31)
    assert aug[0].realtime_end == date(2026, 10, 14)
    assert aug[0].units == meta.units and aug[0].frequency is Frequency.MONTHLY
    assert aug[0].release_id == "10"
    assert all(o.source_snapshot_id.startswith("raw_fred_") for o in obs)
    sep = next(o for o in obs if o.reference_start == date(2026, 9, 1))
    # Records keep the snapshot id of the page they came from (Sep is on page 2).
    assert sep.source_snapshot_id != aug[0].source_snapshot_id
    params = [r.url.params for r in fake_fred.requests if r.url.path.endswith("observations")]
    assert params[0]["output_type"] == "1"
    assert params[0]["realtime_start"] == "1776-07-04"


def test_initial_release_never_replaced_by_revised_value(
    fake_fred: FakeFred, fred_client_factory: Factory
) -> None:
    client, meta, vintages = _setup(fake_fred, fred_client_factory)
    initial = fetch_initial_releases(client, meta, FAKE_TIME, vintages, limit=2)
    by_ref = {o.reference_start: o for o in initial}
    # Today's (revised) value for Aug-2026 is 100.2; the initial release was 100.0.
    assert by_ref[date(2026, 8, 1)].value == 100.0
    assert by_ref[date(2026, 8, 1)].vintage_date == date(2026, 9, 11)
    assert all(o.release_stage is ReleaseStage.INITIAL for o in initial)
    # The initial print is not knowable before its vintage day ends.
    assert not by_ref[date(2026, 8, 1)].is_available_at(datetime(2026, 9, 11, 12, 0, tzinfo=NY))
    assert by_ref[date(2026, 8, 1)].is_available_at(datetime(2026, 9, 12, 0, 0, tzinfo=NY))


def test_latest_only_series_rejected_as_history(fred_client_factory: Factory) -> None:
    fake = FakeFred()
    fake.single("series", "series_SYNTHCPI.json")
    fake.single("series/release", "series_release_SYNTHCPI.json")
    fake.pages("series/vintagedates", ["vintagedates_SYNTHCPI.json"])
    # A "today's data" response: every value stamped with today's real-time period.
    latest = {
        "count": 1,
        "offset": 0,
        "observations": [
            {
                "realtime_start": "2026-11-04",
                "realtime_end": "2026-11-04",
                "date": "2026-08-01",
                "value": "100.2",
            }
        ],
    }
    fake.route("series/observations", lambda p: (200, latest))
    client = fred_client_factory(fake)
    meta = fetch_series_metadata(client, "SYNTHCPI", FAKE_TIME)
    vintages = fetch_vintage_dates(client, "SYNTHCPI", FAKE_TIME)
    with pytest.raises(ResponseSchemaError, match="not a known vintage"):
        fetch_initial_releases(client, meta, FAKE_TIME, vintages)


def test_server_side_initial_release(fred_client_factory: Factory) -> None:
    fake = FakeFred()
    fake.single("series", "series_SYNTHCPI.json")
    fake.single("series/release", "series_release_SYNTHCPI.json")
    fake.pages("series/vintagedates", ["vintagedates_SYNTHCPI.json"])
    good = {
        "count": 2,
        "offset": 0,
        "observations": [
            {
                "realtime_start": "2026-09-11",
                "realtime_end": "9999-12-31",
                "date": "2026-08-01",
                "value": "100.0",
            },
            {
                "realtime_start": "2026-10-15",
                "realtime_end": "9999-12-31",
                "date": "2026-09-01",
                "value": ".",
            },
        ],
    }
    fake.route("series/observations", lambda p: (200, good))
    client = fred_client_factory(fake)
    meta = fetch_series_metadata(client, "SYNTHCPI", FAKE_TIME)
    vintages = fetch_vintage_dates(client, "SYNTHCPI", FAKE_TIME)
    out = fetch_initial_releases(client, meta, FAKE_TIME, vintages, server_side=True)
    assert [(o.reference_start, o.value) for o in out] == [(date(2026, 8, 1), 100.0)]
    assert fake.requests[-1].url.params["output_type"] == "4"

    bad = {
        "count": 1,
        "offset": 0,
        "observations": [
            {
                "realtime_start": "1776-07-04",
                "realtime_end": "9999-12-31",
                "date": "2026-08-01",
                "value": "100.0",
            }
        ],
    }
    fake.route("series/observations", lambda p: (200, bad))
    with pytest.raises(ResponseSchemaError, match="release date is unknown"):
        fetch_initial_releases(client, meta, FAKE_TIME, vintages, server_side=True)


def test_vintage_availability_is_conservative_and_date_level() -> None:
    stamp = vintage_availability(date(2026, 9, 11))
    assert stamp.precision is AvailabilityPrecision.RELEASE_DATE_ONLY
    assert stamp.available_at == datetime(2026, 9, 11, 23, 59, 59, tzinfo=NY)
    assert stamp.raw_available_at == datetime(2026, 9, 11, 0, 0, tzinfo=NY)


def test_reference_period_rules() -> None:
    assert reference_period(date(2026, 4, 1), Frequency.QUARTERLY) == (
        date(2026, 4, 1),
        date(2026, 6, 30),
    )
    assert reference_period(date(2026, 1, 3), Frequency.WEEKLY) == (
        date(2026, 1, 3),
        date(2026, 1, 9),
    )
    with pytest.raises(ResponseSchemaError):
        reference_period(date(2026, 2, 1), Frequency.QUARTERLY)
    with pytest.raises(ResponseSchemaError):
        reference_period(date(2026, 2, 15), Frequency.MONTHLY)
