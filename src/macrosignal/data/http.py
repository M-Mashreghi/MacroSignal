"""Provider-neutral HTTP client with timeout, bounded retry and raw snapshots.

Every successful response is turned into a :class:`RawSnapshot` *before* any
normalization: the raw payload bytes are hashed together with the (redacted)
request metadata, giving a deterministic ``snapshot_id`` that does not depend on
retrieval time or on the caller's API key.  Snapshots can be persisted through
the :class:`~macrosignal.artifacts.ArtifactRegistry` as immutable
``raw_snapshot`` artifacts.

Retry policy: transport errors (timeouts, connection failures) and HTTP
408/425/429/500/502/503/504 are retried with exponential backoff (honouring a
bounded ``Retry-After``) up to ``max_attempts``.  Authentication / client
errors (other 4xx) and response-schema failures are raised immediately and are
never retried.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from macrosignal.artifacts import ArtifactKind, ArtifactRecord, ArtifactRegistry
from macrosignal.domain.manifest import canonical_json, stable_hash

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
DEFAULT_REDACTED_PARAMS = frozenset(
    {"api_key", "apikey", "api-key", "key", "token", "userid", "registrationkey"}
)
REDACTED = "***"
ADAPTER_VERSION = "http-1"

_SOURCE_RE = re.compile(r"[a-z][a-z0-9_]*")
SourceName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


class HttpError(RuntimeError):
    """Base class for client errors."""


class HttpNonRetryableError(HttpError):
    """Authentication/client failure that must not be retried."""

    def __init__(self, status_code: int, url: str) -> None:
        super().__init__(f"non-retryable HTTP {status_code} for {url}")
        self.status_code = status_code


class HttpRetryExhaustedError(HttpError):
    """All retry attempts failed."""


class ResponseSchemaError(HttpError):
    """The response body does not have the expected structure (never retried)."""


class RawSnapshot(BaseModel):
    """Metadata of one raw response, hashed before normalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    source: SourceName
    method: str
    url: str
    params: dict[str, str]
    status_code: int
    content_type: str | None
    payload_sha256: str
    request_hash: str
    retrieved_at: AwareDatetime
    adapter_version: str = ADAPTER_VERSION
    attempts: Annotated[int, Field(ge=1)]


@dataclass(frozen=True)
class RawResponse:
    content: bytes
    snapshot: RawSnapshot

    def json(self) -> Any:
        try:
            return json.loads(self.content)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ResponseSchemaError(
                f"response from {self.snapshot.url} is not valid JSON"
            ) from exc


def redact_params(
    params: Mapping[str, Any] | None, redacted: frozenset[str] = DEFAULT_REDACTED_PARAMS
) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (params or {}).items():
        out[str(key)] = REDACTED if str(key).lower() in redacted else str(value)
    return dict(sorted(out.items()))


def _strip_query(url: str) -> str:
    parts = urlsplit(url)
    if parts.query:
        raise ValueError("pass query parameters via params=, not in the URL (for redaction)")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def request_fingerprint(source: str, method: str, url: str, params: Mapping[str, str]) -> str:
    return stable_hash({"source": source, "method": method.upper(), "url": url, "params": params})


def snapshot_id_for(source: str, request_hash: str, payload_sha256: str) -> str:
    digest = stable_hash({"request": request_hash, "payload": payload_sha256})
    return f"raw_{source}_{digest.removeprefix('sha256:')[:20]}"


class HttpClient:
    """Small synchronous client; inject ``transport``/``sleep``/``clock`` in tests."""

    def __init__(
        self,
        source: str,
        *,
        timeout: float = 30.0,
        max_attempts: int = 4,
        backoff_base: float = 1.0,
        max_backoff: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        redacted_params: frozenset[str] = DEFAULT_REDACTED_PARAMS,
        registry: ArtifactRegistry | None = None,
        user_agent: str = "macrosignal-research/0.1",
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if not _SOURCE_RE.fullmatch(source):
            raise ValueError(f"invalid source name {source!r}")
        self.source = source
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff
        self.sleep = sleep
        self.clock = clock
        self.redacted_params = frozenset(p.lower() for p in redacted_params)
        self.registry = registry
        self._client = httpx.Client(
            timeout=timeout, transport=transport, headers={"User-Agent": user_agent}
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _delay(self, attempt: int, response: httpx.Response | None) -> float:
        delay = min(self.backoff_base * (2 ** (attempt - 1)), self.max_backoff)
        if response is not None:
            retry_after = response.headers.get("Retry-After", "")
            if retry_after.isdigit():
                delay = min(float(retry_after), self.max_backoff)
        return delay

    def get(self, url: str, params: Mapping[str, Any] | None = None) -> RawResponse:
        """GET ``url`` with retries; returns the raw bytes and their snapshot."""
        clean_url = _strip_query(url)
        send_params = {str(k): str(v) for k, v in (params or {}).items()}
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            response: httpx.Response | None = None
            try:
                response = self._client.get(clean_url, params=send_params)
            except httpx.TransportError as exc:
                last_error = exc
            else:
                status = response.status_code
                if 200 <= status < 300:
                    return self._snapshot(clean_url, send_params, response, attempt)
                if status not in RETRYABLE_STATUS:
                    raise HttpNonRetryableError(status, clean_url)
                last_error = HttpError(f"retryable HTTP {status}")
            if attempt < self.max_attempts:
                self.sleep(self._delay(attempt, response))
        raise HttpRetryExhaustedError(
            f"{self.source}: {clean_url} failed after {self.max_attempts} attempts: {last_error}"
        )

    def _snapshot(
        self, url: str, params: Mapping[str, str], response: httpx.Response, attempts: int
    ) -> RawResponse:
        content = response.content
        redacted = redact_params(params, self.redacted_params)
        request_hash = request_fingerprint(self.source, "GET", url, redacted)
        payload_sha = hashlib.sha256(content).hexdigest()
        snapshot = RawSnapshot(
            snapshot_id=snapshot_id_for(self.source, request_hash, payload_sha),
            source=self.source,
            method="GET",
            url=url,
            params=redacted,
            status_code=response.status_code,
            content_type=response.headers.get("Content-Type"),
            payload_sha256=payload_sha,
            request_hash=request_hash,
            retrieved_at=self.clock(),
            attempts=attempts,
        )
        if self.registry is not None:
            persist_snapshot(self.registry, RawResponse(content, snapshot))
        return RawResponse(content, snapshot)


def persist_snapshot(registry: ArtifactRegistry, response: RawResponse) -> ArtifactRecord:
    """Store payload + request metadata as an immutable ``raw_snapshot`` artifact.

    The metadata file excludes retrieval time and attempt count so re-fetching an
    identical payload is an idempotent registration.
    """
    snap = response.snapshot
    meta = snap.model_dump(mode="json", exclude={"retrieved_at", "attempts"})
    return registry.register(
        ArtifactKind.RAW_SNAPSHOT,
        snap.snapshot_id,
        {"payload.bin": response.content, "request.json": canonical_json(meta).encode()},
        created_at=snap.retrieved_at,
        source=snap.source,
        snapshot_id=snap.snapshot_id,
        metadata={"retrieved_at": snap.retrieved_at.isoformat(), "url": snap.url},
    )
