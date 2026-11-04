"""Offline fake FRED/ALFRED API backed by the JSON fixtures in tests/fixtures/fred."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

FRED_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fred"
FAKE_TIME = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)

Route = Callable[[dict[str, str]], tuple[int, Any]]


def load_fred_fixture(name: str) -> Any:
    return json.loads((FRED_FIXTURES / name).read_text(encoding="utf-8"))


class FakeFred:
    """``httpx.MockTransport`` handler that serves FRED-shaped fixture responses.

    Pages of a paginated endpoint are selected by their ``offset`` field. Extra
    routes can be registered per endpoint (path after ``/fred/``) to simulate
    other parameters or failures. Every request is recorded in ``requests``.
    """

    def __init__(self) -> None:
        self.routes: dict[str, Route] = {}
        self.requests: list[httpx.Request] = []

    def route(self, endpoint: str, fn: Route) -> None:
        self.routes[endpoint] = fn

    def pages(self, endpoint: str, files: list[str]) -> None:
        payloads = [load_fred_fixture(f) for f in files]

        def serve(params: dict[str, str]) -> tuple[int, Any]:
            offset = int(params.get("offset", "0"))
            for payload in payloads:
                if payload.get("offset", 0) == offset:
                    return 200, payload
            return 200, {**payloads[-1], "offset": offset, endpoint_key(endpoint): []}

        self.route(endpoint, serve)

    def single(self, endpoint: str, file: str) -> None:
        payload = load_fred_fixture(file)
        self.route(endpoint, lambda params: (200, payload))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        endpoint = request.url.path.split("/fred/", 1)[1]
        params = dict(request.url.params)
        if endpoint not in self.routes:
            return httpx.Response(404, json={"error_code": 404, "error_message": "no route"})
        status, body = self.routes[endpoint](params)
        return httpx.Response(status, json=body)


def endpoint_key(endpoint: str) -> str:
    return {
        "series/observations": "observations",
        "series/vintagedates": "vintage_dates",
        "release/dates": "release_dates",
    }.get(endpoint, "records")
