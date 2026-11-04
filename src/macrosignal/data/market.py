"""Provider-neutral daily market data with one documented demo provider.

:class:`MarketDataProvider` is the interface research layers depend on; an
institutional provider can replace the demo one without touching them.

Demo provider: :class:`YahooDemoProvider` (Yahoo Finance via the optional
``yfinance`` package, extra ``market-demo``).  It is for reproducible
*demonstrations only* (``docs/DATA_LICENSE_POLICY.md``).  Field semantics are
captured explicitly because "adjusted" means different things across
providers; with ``auto_adjust=False`` Yahoo returns:

======================  ==================================  =============================
provider column         canonical field                      adjustment policy
======================  ==================================  =============================
``Open``/``High``/      open / high / low / close            ``split_adjusted`` (prices are
``Low``/``Close``                                            back-adjusted for splits only)
``Adj Close``           adjusted_close                       ``split_and_dividend_adjusted``
``Volume``              volume                               ``split_adjusted``
======================  ==================================  =============================

:func:`normalize_daily_bars` maps provider rows onto the explicit
:class:`~macrosignal.calendar.trading.UsTradingCalendar`: open-type fields are
stamped at the session open, everything else at the session close (13:00 ET on
early-close days).  Rows dated on non-sessions are rejected, sessions without
data inside the coverage window are reported in ``missing_sessions`` (never
filled), and the instrument's coverage/inception comes from the provider's first
valid row (``lifecycle_policy: provider_first_valid``).  The raw provider payload
and metadata are cached as an immutable ``raw_snapshot`` artifact.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from macrosignal.artifacts import ArtifactKind, ArtifactRecord, ArtifactRegistry
from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import (
    AdjustmentPolicy,
    AssetMetadata,
    MarketObservation,
    PriceField,
    ReturnConvention,
)
from macrosignal.domain.manifest import canonical_json

OPEN_FIELDS = frozenset({PriceField.OPEN})


@dataclass(frozen=True)
class RawDailyRow:
    """One provider row: session date plus provider column values (None = missing)."""

    day: date
    values: dict[str, float | None]


@dataclass(frozen=True)
class RawMarketBatch:
    provider: str
    asset_id: str
    rows: tuple[RawDailyRow, ...]
    payload: bytes
    retrieved_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def snapshot_id(self) -> str:
        digest = hashlib.sha256(
            self.payload + canonical_json(self.metadata).encode("utf-8")
        ).hexdigest()
        return f"raw_{self.provider}_{digest[:20]}"


class MarketDataProvider(Protocol):
    name: str
    currency: str
    #: provider column -> (canonical field, adjustment policy)
    field_semantics: dict[str, tuple[PriceField, AdjustmentPolicy]]

    def fetch_daily(self, asset_id: str, start: date, end: date) -> RawMarketBatch: ...


YAHOO_FIELD_SEMANTICS: dict[str, tuple[PriceField, AdjustmentPolicy]] = {
    "Open": (PriceField.OPEN, AdjustmentPolicy.SPLIT_ADJUSTED),
    "High": (PriceField.HIGH, AdjustmentPolicy.SPLIT_ADJUSTED),
    "Low": (PriceField.LOW, AdjustmentPolicy.SPLIT_ADJUSTED),
    "Close": (PriceField.CLOSE, AdjustmentPolicy.SPLIT_ADJUSTED),
    "Adj Close": (PriceField.ADJUSTED_CLOSE, AdjustmentPolicy.SPLIT_AND_DIVIDEND_ADJUSTED),
    "Volume": (PriceField.VOLUME, AdjustmentPolicy.SPLIT_ADJUSTED),
}

Downloader = Callable[[str, date, date], Any]


def _yfinance_download(asset_id: str, start: date, end: date) -> Any:  # pragma: no cover - network
    try:
        import yfinance as yf  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "install the 'market-demo' extra to use the Yahoo demo provider"
        ) from exc
    return yf.Ticker(asset_id).history(
        start=start.isoformat(), end=end.isoformat(), auto_adjust=False, actions=False
    )


class YahooDemoProvider:
    """Yahoo Finance daily bars (demo only); ``download`` is injectable for tests."""

    name = "yahoo_demo"
    currency = "USD"
    field_semantics = YAHOO_FIELD_SEMANTICS

    def __init__(
        self, download: Downloader = _yfinance_download, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._download = download
        self._clock = clock

    def fetch_daily(self, asset_id: str, start: date, end: date) -> RawMarketBatch:
        frame = self._download(asset_id, start, end)
        missing = [c for c in self.field_semantics if c not in frame.columns]
        if missing:
            raise ValueError(f"{self.name}: provider frame lacks columns {missing}")
        rows: list[RawDailyRow] = []
        for ts, rec in frame.iterrows():
            day = ts.date() if hasattr(ts, "date") else date.fromisoformat(str(ts)[:10])
            values: dict[str, float | None] = {}
            for col in self.field_semantics:
                v = rec[col]
                values[col] = None if v != v else float(v)  # NaN -> None
            rows.append(RawDailyRow(day, values))
        payload = frame.to_csv().encode("utf-8")
        retrieved = self._clock() if self._clock else datetime.now().astimezone()
        meta = {
            "provider": self.name,
            "asset_id": asset_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "auto_adjust": False,
            "field_semantics": {
                k: [f.value, a.value] for k, (f, a) in self.field_semantics.items()
            },
            "demo_only": True,
        }
        return RawMarketBatch(self.name, asset_id, tuple(rows), payload, retrieved, meta)


class NormalizedMarketData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset: AssetMetadata
    observations: tuple[MarketObservation, ...]
    missing_sessions: tuple[date, ...]
    missing_values: tuple[tuple[date, str], ...]
    snapshot_id: str
    calendar: str

    def field_series(self, field_: PriceField) -> list[MarketObservation]:
        return [o for o in self.observations if o.field is field_]


def normalize_daily_bars(
    batch: RawMarketBatch,
    provider: MarketDataProvider,
    *,
    role: str,
    calendar: UsTradingCalendar | None = None,
    return_convention: ReturnConvention = ReturnConvention.ADJUSTED_CLOSE_TO_ADJUSTED_CLOSE,
) -> NormalizedMarketData:
    cal = calendar or UsTradingCalendar()
    rows = sorted(batch.rows, key=lambda r: r.day)
    days = [r.day for r in rows]
    if len(set(days)) != len(days):
        raise ValueError(f"{batch.asset_id}: duplicate provider dates")
    bad = [d for d in days if not cal.is_session(d)]
    if bad:
        raise ValueError(f"{batch.asset_id}: provider rows on non-trading days {bad[:5]}")
    valid = [r for r in rows if any(v is not None for v in r.values.values())]
    if not valid:
        raise ValueError(f"{batch.asset_id}: provider returned no valid rows")
    first, last = valid[0].day, valid[-1].day
    if last > batch.retrieved_at.astimezone(cal.timezone).date():
        raise ValueError(f"{batch.asset_id}: provider rows after the retrieval date")
    asset = AssetMetadata(
        asset_id=batch.asset_id,
        role=role,
        provider=batch.provider,
        currency=provider.currency,
        timezone=cal.timezone.key,
        first_tradable_date=first,
        coverage_start=first,
        coverage_end=last,
        price_adjustment_policy=AdjustmentPolicy.SPLIT_AND_DIVIDEND_ADJUSTED,
        return_convention=return_convention,
    )
    snapshot_id = batch.snapshot_id
    observations: list[MarketObservation] = []
    missing_values: list[tuple[date, str]] = []
    for row in valid:
        for column, (field_, policy) in provider.field_semantics.items():
            value = row.values.get(column)
            if value is None:
                missing_values.append((row.day, column))
                continue
            stamp = (
                cal.session_open(row.day) if field_ in OPEN_FIELDS else cal.session_close(row.day)
            )
            obs = MarketObservation(
                asset_id=batch.asset_id,
                timestamp=stamp,
                field=field_,
                value=value,
                currency=provider.currency,
                provider=batch.provider,
                adjustment_policy=policy,
                retrieved_at=batch.retrieved_at,
                snapshot_id=snapshot_id,
            )
            asset.check_observation(obs)
            observations.append(obs)
    present = {r.day for r in valid}
    missing_sessions = tuple(d for d in cal.sessions(first, last) if d not in present)
    return NormalizedMarketData(
        asset=asset,
        observations=tuple(observations),
        missing_sessions=missing_sessions,
        missing_values=tuple(missing_values),
        snapshot_id=snapshot_id,
        calendar=cal.name,
    )


def cache_raw_batch(registry: ArtifactRegistry, batch: RawMarketBatch) -> ArtifactRecord:
    return registry.register(
        ArtifactKind.RAW_SNAPSHOT,
        batch.snapshot_id,
        {
            "payload.csv": batch.payload,
            "provider_metadata.json": canonical_json(batch.metadata).encode("utf-8"),
        },
        created_at=batch.retrieved_at,
        source=batch.provider,
        snapshot_id=batch.snapshot_id,
        metadata={"asset_id": batch.asset_id},
    )


def rows_from_csv(text: str, columns: Sequence[str]) -> list[RawDailyRow]:
    """Parse a ``Date,<columns...>`` CSV (e.g. a cached payload) into raw rows."""
    out: list[RawDailyRow] = []
    for rec in csv.DictReader(io.StringIO(text)):
        day = date.fromisoformat(rec["Date"][:10])
        out.append(
            RawDailyRow(
                day, {c: float(rec[c]) if rec.get(c) not in (None, "") else None for c in columns}
            )
        )
    return out
