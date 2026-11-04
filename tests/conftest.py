"""Shared pytest fixtures (offline fakes live in tests/fakes.py)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from fakes import FAKE_TIME, FakeFred


@pytest.fixture
def fake_fred() -> FakeFred:
    fake = FakeFred()
    fake.single("series", "series_SYNTHCPI.json")
    fake.single("series/release", "series_release_SYNTHCPI.json")
    fake.pages(
        "series/observations", ["observations_SYNTHCPI_p0.json", "observations_SYNTHCPI_p1.json"]
    )
    fake.pages("series/vintagedates", ["vintagedates_SYNTHCPI.json"])
    fake.pages("release/dates", ["release_dates_10.json"])
    return fake


@pytest.fixture
def fred_client_factory() -> Callable[..., Any]:
    from macrosignal.data.fred import FredClient
    from macrosignal.data.http import HttpClient

    def make(fake: FakeFred, **http_kw: Any) -> FredClient:
        http = HttpClient(
            "fred",
            transport=httpx.MockTransport(fake),
            sleep=lambda s: None,
            clock=lambda: FAKE_TIME,
            **http_kw,
        )
        return FredClient(http, "test-key-not-real")

    return make
