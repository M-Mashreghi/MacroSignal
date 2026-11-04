"""Point-in-time as-of query engine (Task 2.12)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from macrosignal.config import load_config_file
from macrosignal.config.models import MacroSeriesRegistry, ReleaseMap
from macrosignal.data.fred_observations import vintage_availability
from macrosignal.domain import AvailabilityPrecision, MacroObservation, ReleaseEvent, ReleaseStage
from macrosignal.fixtures import load_release_stage_fixture, load_vintage_fixture
from macrosignal.pit.as_of import (
    AmbiguousVintageError,
    LookaheadError,
    PitStore,
    assert_no_lookahead,
)
from macrosignal.pit.availability_resolver import AvailabilityResolver
from macrosignal.pit.release_mapping import ReleaseMappingRegistry

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
KEY = ("synthetic_fixture", "TEST_SERIES", date(2026, 8, 1))


def test_pre_initial_and_post_revision_queries() -> None:
    store = PitStore(load_vintage_fixture())
    assert len(store) == 2
    pre = store.as_of(datetime(2026, 9, 1, 8, 29, tzinfo=NY))
    assert KEY not in pre.observations
    initial = store.as_of(datetime(2026, 9, 1, 8, 30, tzinfo=NY))
    assert initial.observations[KEY].value == 100.0
    assert initial.observations[KEY].release_stage is ReleaseStage.INITIAL
    still_initial = store.as_of(datetime(2026, 10, 1, 12, 29, tzinfo=UTC))  # 08:29 ET
    assert still_initial.observations[KEY].value == 100.0
    revised = store.as_of(datetime(2026, 10, 1, 12, 30, tzinfo=UTC))  # 08:30 ET
    assert revised.observations[KEY].value == 101.0
    assert revised.observations[KEY].release_stage is ReleaseStage.REVISION
    assert revised.max_available_at is not None and revised.max_available_at <= revised.as_of


def test_gdp_estimate_stages_selected_by_time() -> None:
    store = PitStore(load_release_stage_fixture())
    series = ("synthetic_fixture", "GDP_LEVEL")

    def stage_at(t: datetime) -> tuple[str, float] | None:
        obs = store.as_of(t, series=[series]).latest(*series)
        return None if obs is None else (obs.release_stage.value, obs.value)

    assert stage_at(datetime(2026, 7, 30, 8, 0, tzinfo=NY)) is None
    assert stage_at(datetime(2026, 7, 30, 9, 0, tzinfo=NY)) == ("advance", 100.0)
    assert stage_at(datetime(2026, 8, 27, 8, 30, tzinfo=NY)) == ("second", 100.7)
    assert stage_at(datetime(2026, 12, 1, tzinfo=NY)) == ("third", 100.5)


def _alfred(value: float, vintage: date, stage: str, **kw: Any) -> MacroObservation:
    data: dict[str, Any] = {
        "source": "fred_alfred",
        "series_id": "CPIAUCSL",
        "retrieved_at": datetime(2026, 12, 1, tzinfo=UTC),
        "source_snapshot_id": "raw_fred_x",
        "adapter_version": "t",
        "release_stage": stage,
        "reference_start": date(2026, 9, 1),
        "reference_end": date(2026, 9, 30),
        "value": value,
        "units": "index",
        "frequency": "monthly",
        "seasonal_adjustment": "seasonally_adjusted",
        "availability": vintage_availability(vintage),
        "vintage_date": vintage,
        "realtime_start": vintage,
    }
    data.update(kw)
    return MacroObservation.model_validate(data)


def test_resolved_exact_vs_date_level_queries() -> None:
    mapping = ReleaseMappingRegistry(
        load_config_file(ROOT / "configs/series/us_macro_v1.yaml", MacroSeriesRegistry),
        load_config_file(ROOT / "configs/series/release_map_v2.yaml", ReleaseMap),
    )
    event = ReleaseEvent(
        release_id="CPI-2026-09",
        release_family="CPI",
        release_name="CPI",
        source="bls",
        calendar_snapshot_id="cal",
        source_timezone="America/New_York",
        scheduled_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        actual_release_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        reference_start=date(2026, 9, 1),
        reference_end=date(2026, 9, 30),
        release_stage="initial",
    )
    resolved = AvailabilityResolver(mapping, [event]).resolve_all(
        [
            _alfred(320.0, date(2026, 10, 15), "initial"),
            _alfred(320.4, date(2026, 11, 13), "revision"),
        ]
    )
    store = PitStore(resolved)
    key = ("fred_alfred", "CPIAUCSL", date(2026, 9, 1))
    assert store.as_of(datetime(2026, 10, 15, 8, 29, tzinfo=NY)).observations == {}
    assert store.as_of(datetime(2026, 10, 15, 8, 31, tzinfo=NY)).observations[key].value == 320.0
    # The revision is only date-level: not knowable until the end of its vintage day.
    assert store.as_of(datetime(2026, 11, 13, 12, 0, tzinfo=NY)).observations[key].value == 320.0
    assert store.as_of(datetime(2026, 11, 14, 0, 0, tzinfo=NY)).observations[key].value == 320.4
    strict = store.as_of(
        datetime(2026, 11, 14, tzinfo=NY), min_precision=AvailabilityPrecision.EXACT_TIMESTAMP
    )
    assert strict.observations == {} and strict.excluded_for_precision == (key,)


def test_series_filter_and_vintage_chain() -> None:
    store = PitStore(load_vintage_fixture() + load_release_stage_fixture())
    res = store.as_of(
        datetime(2027, 1, 1, tzinfo=UTC), series=[("synthetic_fixture", "TEST_SERIES")]
    )
    assert {k[1] for k in res.observations} == {"TEST_SERIES"}
    chain = store.vintages(*KEY)
    assert [o.value for o in chain] == [100.0, 101.0]


def test_adding_same_vintage_twice_is_idempotent() -> None:
    obs = load_vintage_fixture()
    store = PitStore(obs)
    store.add(obs)
    assert len(store) == 2


def test_ambiguous_same_instant_values_rejected() -> None:
    a = _alfred(1.0, date(2026, 10, 15), "initial")
    b = _alfred(2.0, date(2026, 10, 15), "initial", source_snapshot_id="raw_other")
    with pytest.raises(AmbiguousVintageError):
        PitStore([a, b]).as_of(datetime(2026, 12, 1, tzinfo=UTC))


def test_lookahead_guard_and_naive_times() -> None:
    obs = load_vintage_fixture()
    with pytest.raises(LookaheadError, match="TEST_SERIES"):
        assert_no_lookahead(obs, datetime(2026, 9, 15, tzinfo=NY))
    assert_no_lookahead(obs, datetime(2026, 10, 2, tzinfo=NY))
    with pytest.raises(ValueError, match="timezone-aware"):
        PitStore(obs).as_of(datetime(2026, 10, 2))


def test_every_as_of_respects_golden_rule() -> None:
    store = PitStore(load_vintage_fixture() + load_release_stage_fixture())
    t = datetime(2026, 7, 1, tzinfo=UTC)
    while t < datetime(2026, 11, 1, tzinfo=UTC):
        res = store.as_of(t)
        assert all(o.availability.available_at <= t for o in res.observations.values())
        t += timedelta(hours=7)
