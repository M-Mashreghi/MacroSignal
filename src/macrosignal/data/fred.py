"""FRED / ALFRED API transport client.

This module only *transports*: it builds authenticated requests, follows
pagination, checks the response envelope, and returns the raw JSON records with
the ids of the raw snapshots they came from.  Turning those records into
canonical domain objects (metadata, vintages, observations) is the job of the
normalization tasks (2.3-2.5).

Endpoints used (https://fred.stlouisfed.org/docs/api/fred/):

* ``fred/series``                - series metadata
* ``fred/series/release``        - release a series belongs to
* ``fred/series/observations``   - observations, with ALFRED real-time
  parameters (``realtime_start`` / ``realtime_end`` / ``vintage_dates`` /
  ``output_type``)
* ``fred/series/vintagedates``   - ALFRED vintage dates
* ``fred/release/dates``         - release dates of a release

The API key is required, is sent only as a request parameter and is redacted
from every stored snapshot by :class:`~macrosignal.data.http.HttpClient`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic import SecretStr

from macrosignal.config.models import MacroSeriesRegistry
from macrosignal.config.settings import Settings
from macrosignal.data.http import HttpClient, ResponseSchemaError

FRED_BASE_URL = "https://api.stlouisfed.org/fred"
FRED_PROVIDER = "fred_alfred"
OBSERVATIONS_PAGE_LIMIT = 100_000
DEFAULT_PAGE_LIMIT = 10_000

#: ``output_type`` values of fred/series/observations.
OUTPUT_OBSERVATIONS_BY_REALTIME = 1
OUTPUT_ALL_BY_VINTAGE = 2
OUTPUT_NEW_AND_REVISED_BY_VINTAGE = 3
OUTPUT_INITIAL_RELEASE_ONLY = 4


class MissingCredentialError(RuntimeError):
    """A required API key is not configured (never invent one)."""


class FredApiError(RuntimeError):
    """FRED returned an error envelope."""


@dataclass(frozen=True)
class FredResult:
    """Raw records from one logical request plus the raw snapshots they came from."""

    records: list[Any]
    snapshot_ids: tuple[str, ...]
    envelope: dict[str, Any] = field(default_factory=dict)


def configured_series_ids(registry: MacroSeriesRegistry) -> list[str]:
    """FRED/ALFRED series ids declared in the macro series registry (sorted, unique)."""
    return sorted({s.series_id for s in registry.series if s.provider == FRED_PROVIDER})


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


class FredClient:
    """Authenticated FRED/ALFRED requests with pagination and envelope checks."""

    def __init__(
        self,
        http: HttpClient,
        api_key: SecretStr | str | None,
        *,
        base_url: str = FRED_BASE_URL,
    ) -> None:
        key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        if not key:
            raise MissingCredentialError(
                "FRED_API_KEY is not configured; set it in the environment or a local .env"
            )
        self._key = key
        self.http = http
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_settings(cls, settings: Settings, http: HttpClient) -> FredClient:
        return cls(http, settings.fred_api_key)

    # --- transport ------------------------------------------------------------------
    def _request(self, endpoint: str, params: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
        query = {k: v for k, v in params.items() if v is not None}
        query.update({"api_key": self._key, "file_type": "json"})
        response = self.http.get(f"{self.base_url}/{endpoint}", query)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ResponseSchemaError(f"FRED {endpoint}: expected a JSON object")
        if "error_code" in payload or "error_message" in payload:
            raise FredApiError(
                f"FRED {endpoint}: {payload.get('error_code')} {payload.get('error_message')}"
            )
        return payload, response.snapshot.snapshot_id

    def _single(self, endpoint: str, key: str, params: Mapping[str, Any]) -> FredResult:
        payload, snap = self._request(endpoint, params)
        records = payload.get(key)
        if not isinstance(records, list):
            raise ResponseSchemaError(f"FRED {endpoint}: missing list field {key!r}")
        return FredResult(records=records, snapshot_ids=(snap,), envelope=_envelope(payload, key))

    def _paginated(
        self, endpoint: str, key: str, params: Mapping[str, Any], limit: int
    ) -> FredResult:
        records: list[Any] = []
        snapshots: list[str] = []
        offset = 0
        envelope: dict[str, Any] = {}
        while True:
            payload, snap = self._request(endpoint, {**params, "limit": limit, "offset": offset})
            snapshots.append(snap)
            page = payload.get(key)
            count = payload.get("count")
            if not isinstance(page, list) or not isinstance(count, int):
                raise ResponseSchemaError(f"FRED {endpoint}: missing {key!r} list or count")
            envelope = _envelope(payload, key)
            records.extend(page)
            offset += len(page)
            if offset >= count:
                break
            if not page:
                raise ResponseSchemaError(
                    f"FRED {endpoint}: empty page at offset {offset} before count {count}"
                )
        if len(records) != envelope.get("count", len(records)):
            raise ResponseSchemaError(f"FRED {endpoint}: record count mismatch")
        return FredResult(records=records, snapshot_ids=tuple(snapshots), envelope=envelope)

    # --- endpoints ----------------------------------------------------------------------
    def series(
        self, series_id: str, realtime_start: date | None = None, realtime_end: date | None = None
    ) -> FredResult:
        return self._single(
            "series",
            "seriess",
            {
                "series_id": series_id,
                "realtime_start": _iso(realtime_start),
                "realtime_end": _iso(realtime_end),
            },
        )

    def series_release(self, series_id: str) -> FredResult:
        return self._single("series/release", "releases", {"series_id": series_id})

    def observations(
        self,
        series_id: str,
        *,
        realtime_start: date | None = None,
        realtime_end: date | None = None,
        vintage_dates: Sequence[date] | None = None,
        observation_start: date | None = None,
        observation_end: date | None = None,
        output_type: int | None = None,
        limit: int = OBSERVATIONS_PAGE_LIMIT,
    ) -> FredResult:
        if vintage_dates is not None and (realtime_start or realtime_end):
            raise ValueError("vintage_dates cannot be combined with realtime_start/realtime_end")
        if output_type is not None and output_type not in (1, 2, 3, 4):
            raise ValueError(f"unsupported output_type {output_type}")
        params = {
            "series_id": series_id,
            "realtime_start": _iso(realtime_start),
            "realtime_end": _iso(realtime_end),
            "vintage_dates": ",".join(d.isoformat() for d in vintage_dates)
            if vintage_dates
            else None,
            "observation_start": _iso(observation_start),
            "observation_end": _iso(observation_end),
            "output_type": output_type,
            "sort_order": "asc",
        }
        return self._paginated("series/observations", "observations", params, limit)

    def vintage_dates(
        self,
        series_id: str,
        *,
        realtime_start: date | None = None,
        realtime_end: date | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> FredResult:
        params = {
            "series_id": series_id,
            "realtime_start": _iso(realtime_start or date(1776, 7, 4)),
            "realtime_end": _iso(realtime_end or date(9999, 12, 31)),
            "sort_order": "asc",
        }
        return self._paginated("series/vintagedates", "vintage_dates", params, limit)

    def release_dates(self, release_id: int, *, limit: int = DEFAULT_PAGE_LIMIT) -> FredResult:
        params = {
            "release_id": release_id,
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
            "include_release_dates_with_no_data": "true",
            "sort_order": "asc",
        }
        return self._paginated("release/dates", "release_dates", params, limit)

    def series_metadata_for(self, series_ids: Iterable[str]) -> dict[str, FredResult]:
        """Fetch ``fred/series`` for each id (e.g. ``configured_series_ids(registry)``)."""
        return {sid: self.series(sid) for sid in series_ids}


def _envelope(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k != key}
