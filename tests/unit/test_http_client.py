"""HTTP client retry policy and raw snapshot layer (Task 2.1)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from macrosignal.artifacts import ArtifactKind, ArtifactRegistry
from macrosignal.data.http import (
    REDACTED,
    HttpClient,
    HttpNonRetryableError,
    HttpRetryExhaustedError,
    ResponseSchemaError,
    redact_params,
)

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
URL = "https://api.example.test/series/observations"


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    sleeps: list[float] | None = None,
    **kw: object,
) -> HttpClient:
    record = sleeps if sleeps is not None else []
    options: dict[str, object] = {"clock": lambda: T0, **kw}
    return HttpClient(
        "example",
        transport=httpx.MockTransport(handler),
        sleep=record.append,
        **options,  # type: ignore[arg-type]
    )


def _sequence(
    responses: list[httpx.Response | Exception],
) -> Callable[[httpx.Request], httpx.Response]:
    calls = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        item = next(calls)
        if isinstance(item, Exception):
            raise item
        return item

    return handler


def test_success_builds_deterministic_snapshot() -> None:
    body = b'{"observations": []}'
    handler = _sequence(
        [httpx.Response(200, content=body, headers={"Content-Type": "application/json"})] * 2
    )
    c1 = _client(handler)
    r1 = c1.get(URL, {"series_id": "CPIAUCSL", "api_key": "secret-one"})
    r2 = _client(
        _sequence([httpx.Response(200, content=body)]),
        clock=lambda: datetime(2027, 1, 1, tzinfo=UTC),
    ).get(URL, {"api_key": "secret-two", "series_id": "CPIAUCSL"})
    assert r1.json() == {"observations": []}
    assert r1.snapshot.params == {"api_key": REDACTED, "series_id": "CPIAUCSL"}
    # Same payload + request (keys redacted) => same id regardless of key or time.
    assert r1.snapshot.snapshot_id == r2.snapshot.snapshot_id
    assert r1.snapshot.snapshot_id.startswith("raw_example_")
    assert r1.snapshot.attempts == 1
    assert "secret" not in r1.snapshot.model_dump_json()


def test_payload_change_changes_snapshot_id() -> None:
    a = _client(_sequence([httpx.Response(200, content=b"1")])).get(URL, {"x": "1"})
    b = _client(_sequence([httpx.Response(200, content=b"2")])).get(URL, {"x": "1"})
    c = _client(_sequence([httpx.Response(200, content=b"1")])).get(URL, {"x": "2"})
    assert len({a.snapshot.snapshot_id, b.snapshot.snapshot_id, c.snapshot.snapshot_id}) == 3
    assert a.snapshot.request_hash != c.snapshot.request_hash


def test_retries_transient_failures_with_backoff() -> None:
    sleeps: list[float] = []
    handler = _sequence(
        [
            httpx.ConnectTimeout("timeout"),
            httpx.Response(503),
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, content=b"ok"),
        ]
    )
    resp = _client(handler, sleeps, backoff_base=0.5).get(URL)
    assert resp.content == b"ok"
    assert resp.snapshot.attempts == 4
    assert sleeps == [0.5, 1.0, 7.0]


def test_retry_exhaustion_is_bounded() -> None:
    sleeps: list[float] = []
    handler = _sequence([httpx.Response(500)] * 3)
    with pytest.raises(HttpRetryExhaustedError, match="after 3 attempts"):
        _client(handler, sleeps, max_attempts=3).get(URL)
    assert len(sleeps) == 2


def test_backoff_capped() -> None:
    sleeps: list[float] = []
    handler = _sequence([httpx.Response(502)] * 5 + [httpx.Response(200, content=b"x")])
    _client(handler, sleeps, max_attempts=6, backoff_base=4, max_backoff=10).get(URL)
    assert sleeps == [4, 8, 10, 10, 10]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_auth_and_client_errors_not_retried(status: int) -> None:
    sleeps: list[float] = []
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status)

    with pytest.raises(HttpNonRetryableError) as info:
        _client(handler, sleeps).get(URL, {"api_key": "k"})
    assert info.value.status_code == status
    assert calls == [1] and sleeps == []
    assert "k" not in str(info.value).replace(URL, "")


def test_schema_failure_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, content=b"<html>maintenance</html>")

    resp = _client(handler).get(URL)
    with pytest.raises(ResponseSchemaError):
        resp.json()
    assert calls == [1]


def test_query_in_url_rejected() -> None:
    with pytest.raises(ValueError, match="params="):
        _client(_sequence([])).get(URL + "?api_key=abc")


def test_params_are_sent_to_server() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"{}")

    _client(handler).get(URL, {"api_key": "real", "limit": 10})
    assert seen[0].url.params["api_key"] == "real"
    assert seen[0].url.params["limit"] == "10"


def test_snapshot_persisted_immutably(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path / "data", tmp_path / "reports")
    body = b'{"a": 1}'
    resp = _client(_sequence([httpx.Response(200, content=body)]), registry=registry).get(
        URL, {"api_key": "k1"}
    )
    later = _client(
        _sequence([httpx.Response(200, content=body)]),
        registry=registry,
        clock=lambda: datetime(2026, 12, 1, tzinfo=UTC),
    ).get(URL, {"api_key": "k2"})
    assert later.snapshot.snapshot_id == resp.snapshot.snapshot_id
    record = registry.get(resp.snapshot.snapshot_id)
    assert record.kind is ArtifactKind.RAW_SNAPSHOT
    assert record.source == "example"
    files = registry.read_files(record.artifact_id)
    assert files["payload.bin"] == body
    assert b"k1" not in files["request.json"]
    assert len(registry.records()) == 1


def test_redact_params_case_insensitive() -> None:
    assert redact_params({"API_KEY": "x", "b": 2}) == {"API_KEY": REDACTED, "b": "2"}


def test_invalid_source_name() -> None:
    with pytest.raises(ValueError, match="source"):
        HttpClient("Bad Source")
