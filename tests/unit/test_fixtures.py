"""Synthetic point-in-time fixture suite (Task 1.11)."""

from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from macrosignal.domain import (
    Frequency,
    ReleaseStage,
    SurpriseMode,
    check_pre_release,
)
from macrosignal.fixtures import (
    FIXTURE_FILES,
    fixture_asset,
    fixtures_dir,
    known_at,
    load_consensus_fixture,
    load_market_price_fixture,
    load_ragged_edge_fixture,
    load_release_calendar_fixture,
    load_release_stage_fixture,
    load_state_alignment_fixture,
    load_vintage_fixture,
    parse_reference_period,
)

NY = ZoneInfo("America/New_York")


def test_all_fixture_files_present() -> None:
    for name in FIXTURE_FILES.values():
        assert (fixtures_dir() / name).is_file(), name


def test_parse_reference_period() -> None:
    assert parse_reference_period("2026-09") == (
        date(2026, 9, 1),
        date(2026, 9, 30),
        Frequency.MONTHLY,
    )
    assert parse_reference_period("2026-Q2") == (
        date(2026, 4, 1),
        date(2026, 6, 30),
        Frequency.QUARTERLY,
    )
    with pytest.raises(ValueError):
        parse_reference_period("2026-Q5")


def test_vintage_reconstruction_never_uses_later_revision() -> None:
    obs = load_vintage_fixture()
    assert [o.release_stage for o in obs] == [ReleaseStage.INITIAL, ReleaseStage.REVISION]
    key = ("TEST_SERIES", date(2026, 8, 1))
    assert known_at(obs, datetime(2026, 8, 31, 23, 59, tzinfo=NY)) == {}
    assert known_at(obs, datetime(2026, 9, 15, tzinfo=NY))[key].value == 100.0
    # One minute before the revision is published the initial print is still current.
    assert known_at(obs, datetime(2026, 10, 1, 8, 29, tzinfo=NY))[key].value == 100.0
    assert known_at(obs, datetime(2026, 10, 1, 8, 30, tzinfo=NY))[key].value == 101.0


def test_release_stages_ordered_and_available_in_turn() -> None:
    stages = load_release_stage_fixture()
    assert [s.release_stage.value for s in stages] == ["advance", "second", "third"]
    times = [s.availability.available_at for s in stages]
    assert times == sorted(times)
    assert all(s.frequency is Frequency.QUARTERLY for s in stages)
    as_of = datetime(2026, 9, 1, tzinfo=NY)
    assert [s.release_stage.value for s in stages if s.is_available_at(as_of)] == [
        "advance",
        "second",
    ]


def test_release_calendar_events() -> None:
    (event,) = load_release_calendar_fixture()
    assert event.release_id == "CPI-2026-09"
    assert event.scheduled_at_utc.hour == 12
    assert event.is_released


def test_ragged_edge_rows_have_heterogeneous_ages() -> None:
    rows = load_ragged_edge_fixture()
    ages = {r.feature_name: r.age_since_available_days for r in rows}
    assert ages == {"cpi_yoy": 1, "payroll_change": 13, "gdp_qoq_ann": 20}
    for r in rows:
        assert r.available_at <= r.as_of
        assert (r.as_of.date() - r.available_at.date()).days == r.age_since_available_days


def test_market_prices_respect_asset_lifecycle() -> None:
    asset = fixture_asset()
    prices = load_market_price_fixture()
    assert len(prices) == 9
    for p in prices:
        asset.check_observation(p)


def test_consensus_is_pre_release() -> None:
    (exp,) = load_consensus_fixture()
    (event,) = load_release_calendar_fixture()
    check_pre_release(exp, event, SurpriseMode.MARKET_SURPRISE)


def test_state_alignment_descriptors() -> None:
    rows = load_state_alignment_fixture()
    assert {r.fit_id for r in rows} == {"fit_A", "fit_B"}
    fit_b = [r for r in rows if r.fit_id == "fit_B"]
    assert all(r.prior_canonical_state is None for r in fit_b)
    # Raw ids are permuted between fits: fit_B state 1 resembles fit_A state 0.
    a0 = next(r for r in rows if r.fit_id == "fit_A" and r.raw_state_id == 0)
    b1 = next(r for r in fit_b if r.raw_state_id == 1)
    assert (a0.growth_factor > 0) == (b1.growth_factor > 0)


def test_loaders_are_deterministic() -> None:
    assert load_vintage_fixture() == load_vintage_fixture()
    assert load_market_price_fixture() == load_market_price_fixture()


def test_loaders_accept_custom_directory(tmp_path: Path) -> None:
    for name in FIXTURE_FILES.values():
        shutil.copy(fixtures_dir() / name, tmp_path / name)
    assert load_vintage_fixture(tmp_path) == load_vintage_fixture()
