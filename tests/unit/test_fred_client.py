"""FRED / ALFRED transport client against synthetic fixtures (Task 2.2)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from fakes import FakeFred, load_fred_fixture
from macrosignal.artifacts import ArtifactRegistry
from macrosignal.config import Settings, load_config_file
from macrosignal.config.models import MacroSeriesRegistry
from macrosignal.data.fred import (
    OUTPUT_INITIAL_RELEASE_ONLY,
    FredApiError,
    FredClient,
    MissingCredentialError,
    configured_series_ids,
)
from macrosignal.data.http import HttpClient, HttpNonRetryableError, ResponseSchemaError

ROOT = Path(__file__).resolve().parents[2]
Factory = Callable[..., FredClient]


def test_missing_key_is_an_error_not_a_guess() -> None:
    http = HttpClient("fred")
    with pytest.raises(MissingCredentialError, match="FRED_API_KEY"):
        FredClient(http, None)
    with pytest.raises(MissingCredentialError):
        FredClient(http, "")
    with pytest.raises(MissingCredentialError):
        FredClient.from_settings(Settings(_env_file=None, fred_api_key=None), http)  # type: ignore[call-arg]


def test_series_metadata_request(fake_fred: FakeFred, fred_client_factory: Factory) -> None:
    client = fred_client_factory(fake_fred)
    result = client.series("SYNTHCPI")
    assert result.records[0]["id"] == "SYNTHCPI"
    assert len(result.snapshot_ids) == 1
    sent = fake_fred.requests[0].url.params
    assert sent["api_key"] == "test-key-not-real"
    assert sent["file_type"] == "json"
    assert sent["series_id"] == "SYNTHCPI"
    assert "realtime_start" not in sent  # None params are not sent


def test_observations_follow_pagination(fake_fred: FakeFred, fred_client_factory: Factory) -> None:
    client = fred_client_factory(fake_fred)
    result = client.observations(
        "SYNTHCPI", realtime_start=date(1776, 7, 4), realtime_end=date(9999, 12, 31), limit=2
    )
    assert [r["value"] for r in result.records] == ["100.0", "100.2", "100.5"]
    assert len(result.snapshot_ids) == 2
    offsets = [r.url.params["offset"] for r in fake_fred.requests]
    assert offsets == ["0", "2"]
    assert fake_fred.requests[0].url.params["limit"] == "2"
    assert result.envelope["count"] == 3


def test_observation_parameters(fake_fred: FakeFred, fred_client_factory: Factory) -> None:
    client = fred_client_factory(fake_fred)
    client.observations(
        "SYNTHCPI",
        vintage_dates=[date(2026, 9, 11), date(2026, 10, 15)],
        output_type=OUTPUT_INITIAL_RELEASE_ONLY,
        limit=2,
    )
    sent = fake_fred.requests[0].url.params
    assert sent["vintage_dates"] == "2026-09-11,2026-10-15"
    assert sent["output_type"] == "4"
    with pytest.raises(ValueError, match="cannot be combined"):
        client.observations(
            "SYNTHCPI", vintage_dates=[date(2026, 9, 11)], realtime_start=date(2026, 1, 1)
        )
    with pytest.raises(ValueError, match="output_type"):
        client.observations("SYNTHCPI", output_type=9)


def test_vintage_and_release_dates(fake_fred: FakeFred, fred_client_factory: Factory) -> None:
    client = fred_client_factory(fake_fred)
    assert client.vintage_dates("SYNTHCPI").records == ["2026-09-11", "2026-10-15"]
    sent = fake_fred.requests[-1].url.params
    assert sent["realtime_start"] == "1776-07-04" and sent["realtime_end"] == "9999-12-31"
    assert [r["date"] for r in client.release_dates(10).records] == ["2026-09-11", "2026-10-15"]
    assert client.series_release("SYNTHCPI").records[0]["id"] == 10


def test_error_envelope_and_http_errors(fred_client_factory: Factory) -> None:
    fake = FakeFred()
    fake.route("series", lambda p: (200, load_fred_fixture("error_bad_series.json")))
    with pytest.raises(FredApiError, match="does not exist"):
        fred_client_factory(fake).series("NOPE")
    fake.route("series", lambda p: (400, load_fred_fixture("error_bad_series.json")))
    with pytest.raises(HttpNonRetryableError):
        fred_client_factory(fake).series("NOPE")


def test_schema_failures(fred_client_factory: Factory) -> None:
    fake = FakeFred()
    fake.route("series", lambda p: (200, {"unexpected": True}))
    with pytest.raises(ResponseSchemaError, match="seriess"):
        fred_client_factory(fake).series("SYNTHCPI")
    fake.route("series/observations", lambda p: (200, {"count": 5, "observations": []}))
    with pytest.raises(ResponseSchemaError, match="empty page"):
        fred_client_factory(fake).observations("SYNTHCPI")


def test_snapshots_redact_key(
    fake_fred: FakeFred, tmp_path: Path, fred_client_factory: Factory
) -> None:
    registry = ArtifactRegistry(tmp_path / "data", tmp_path / "reports")
    client = fred_client_factory(fake_fred, registry=registry)
    result = client.series("SYNTHCPI")
    files = registry.read_files(result.snapshot_ids[0])
    assert b"test-key-not-real" not in files["request.json"]
    assert registry.get(result.snapshot_ids[0]).source == "fred"


def test_configured_series_ids() -> None:
    registry = load_config_file(ROOT / "configs/series/us_macro_v1.yaml", MacroSeriesRegistry)
    ids = configured_series_ids(registry)
    assert "CPIAUCSL" in ids and "PAYEMS" in ids
    assert ids == sorted(set(ids))


def test_series_metadata_for(fake_fred: FakeFred, fred_client_factory: Factory) -> None:
    out: dict[str, Any] = fred_client_factory(fake_fred).series_metadata_for(["SYNTHCPI"])
    assert set(out) == {"SYNTHCPI"}
