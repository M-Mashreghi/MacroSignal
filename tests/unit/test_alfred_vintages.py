"""ALFRED vintage-date retrieval and revision history (Task 2.4)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from fakes import FAKE_TIME, FakeFred
from macrosignal.artifacts import ArtifactKind, ArtifactRegistry
from macrosignal.config import load_config_file
from macrosignal.config.models import MacroSeriesRegistry
from macrosignal.data.alfred import (
    VintageDateSet,
    fetch_pit_vintage_dates,
    fetch_vintage_dates,
    persist_vintage_dates,
    pit_series_ids,
    vintage_history,
)
from macrosignal.data.fred import FredClient
from macrosignal.data.http import ResponseSchemaError

ROOT = Path(__file__).resolve().parents[2]
Factory = Callable[..., FredClient]


def test_fetch_vintage_dates(fake_fred: FakeFred, fred_client_factory: Factory) -> None:
    vds = fetch_vintage_dates(fred_client_factory(fake_fred), "SYNTHCPI", FAKE_TIME)
    assert vds.vintage_dates == (date(2026, 9, 11), date(2026, 10, 15))
    assert vds.snapshot_ids and vds.snapshot_ids[0].startswith("raw_fred_")
    assert vds.latest_as_of(date(2026, 9, 10)) is None
    assert vds.latest_as_of(date(2026, 10, 14)) == date(2026, 9, 11)
    assert vds.latest_as_of(date(2026, 10, 15)) == date(2026, 10, 15)
    assert vds.between(date(2026, 10, 1), date(2026, 12, 1)) == (date(2026, 10, 15),)


@pytest.mark.parametrize(
    "dates",
    [["2026-10-15", "2026-09-11"], ["2026-09-11", "2026-09-11"], [], ["2026/09/11"]],
)
def test_bad_vintage_lists_rejected(dates: list[str], fred_client_factory: Factory) -> None:
    fake = FakeFred()
    fake.route(
        "series/vintagedates",
        lambda p: (200, {"count": len(dates), "offset": 0, "vintage_dates": dates}),
    )
    with pytest.raises(ResponseSchemaError):
        fetch_vintage_dates(fred_client_factory(fake), "SYNTHCPI", FAKE_TIME)


def test_vintage_set_invariants() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        VintageDateSet(
            series_id="X",
            vintage_dates=(date(2026, 2, 1), date(2026, 1, 1)),
            snapshot_ids=("s",),
            retrieved_at=FAKE_TIME,
        )
    with pytest.raises(ValueError, match="after the retrieval date"):
        VintageDateSet(
            series_id="X",
            vintage_dates=(date(2027, 1, 1),),
            snapshot_ids=("s",),
            retrieved_at=FAKE_TIME,
        )


def test_pit_required_series_selected(fake_fred: FakeFred, fred_client_factory: Factory) -> None:
    registry = load_config_file(ROOT / "configs/series/us_macro_v1.yaml", MacroSeriesRegistry)
    expected = sorted(
        {s.series_id for s in registry.series if s.pit_required and s.provider == "fred_alfred"}
    )
    assert pit_series_ids(registry) == expected
    out = fetch_pit_vintage_dates(fred_client_factory(fake_fred), registry, FAKE_TIME)
    assert set(out) == set(expected)
    requested = {r.url.params["series_id"] for r in fake_fred.requests}
    assert requested == set(expected)


def test_persisted_idempotently(
    fake_fred: FakeFred, tmp_path: Path, fred_client_factory: Factory
) -> None:
    reg = ArtifactRegistry(tmp_path / "data", tmp_path / "reports")
    vds = fetch_vintage_dates(fred_client_factory(fake_fred), "SYNTHCPI", FAKE_TIME)
    rec = persist_vintage_dates(reg, vds)
    again = persist_vintage_dates(
        reg, vds.model_copy(update={"retrieved_at": datetime(2026, 12, 1, tzinfo=UTC)})
    )
    assert rec == again
    assert rec.kind is ArtifactKind.NORMALIZED
    assert reg.path_of(rec).as_posix().endswith(f"processed/normalized/{vds.artifact_id}")


def test_multiple_vintages_of_same_reference_kept_in_order(
    fake_fred: FakeFred, fred_client_factory: Factory
) -> None:
    client = fred_client_factory(fake_fred)
    vds = fetch_vintage_dates(client, "SYNTHCPI", FAKE_TIME)
    obs = client.observations(
        "SYNTHCPI", realtime_start=date(1776, 7, 4), realtime_end=date(9999, 12, 31), limit=2
    )
    history = vintage_history(obs.records, vds)
    aug = history[date(2026, 8, 1)]
    assert [(v.realtime_start, v.value) for v in aug] == [
        (date(2026, 9, 11), 100.0),
        (date(2026, 10, 15), 100.2),
    ]
    assert aug[0].realtime_end == date(2026, 10, 14)
    assert [v.value for v in history[date(2026, 9, 1)]] == [100.5]


def test_three_vintage_chain_and_missing_value() -> None:
    records = [
        {
            "date": "2026-06-01",
            "realtime_start": "2026-09-11",
            "realtime_end": "9999-12-31",
            "value": "5.2",
        },
        {
            "date": "2026-06-01",
            "realtime_start": "2026-07-15",
            "realtime_end": "2026-08-14",
            "value": "5.0",
        },
        {
            "date": "2026-06-01",
            "realtime_start": "2026-08-15",
            "realtime_end": "2026-09-10",
            "value": ".",
        },
    ]
    chain = vintage_history(records)[date(2026, 6, 1)]
    assert [v.value for v in chain] == [5.0, None, 5.2]


def test_overlap_and_unknown_vintage_rejected() -> None:
    overlapping = [
        {
            "date": "2026-06-01",
            "realtime_start": "2026-07-15",
            "realtime_end": "2026-08-20",
            "value": "1",
        },
        {
            "date": "2026-06-01",
            "realtime_start": "2026-08-15",
            "realtime_end": "9999-12-31",
            "value": "2",
        },
    ]
    with pytest.raises(ResponseSchemaError, match="overlapping"):
        vintage_history(overlapping)
    vds = VintageDateSet(
        series_id="X",
        vintage_dates=(date(2026, 7, 15),),
        snapshot_ids=("s",),
        retrieved_at=FAKE_TIME,
    )
    with pytest.raises(ResponseSchemaError, match="not a known vintage"):
        vintage_history(overlapping[1:], vds)
    with pytest.raises(ResponseSchemaError, match="missing"):
        vintage_history([{"date": "2026-06-01"}])
