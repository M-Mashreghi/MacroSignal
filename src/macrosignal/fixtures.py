"""Loaders for the bundled synthetic point-in-time fixtures in ``examples/``.

The CSVs under ``examples/`` are tiny, synthetic and deterministic (see
``examples/README.md``); they are *not* historical data.  These helpers turn
them into canonical domain objects so unit/integration tests can exercise
vintages, release stages, release calendars, ragged-edge feature rows, market
prices, expectations and regime state-alignment descriptors without any
external API.

All provenance fields that the CSVs do not carry are filled with fixed,
clearly-labelled fixture values (``FIXTURE_*``) so results are reproducible.
"""

from __future__ import annotations

import calendar
import csv
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat

from macrosignal.config import find_project_root
from macrosignal.domain import (
    AdjustmentPolicy,
    AssetMetadata,
    AvailabilityPrecision,
    AvailabilitySource,
    AvailabilityStamp,
    ConsensusExpectation,
    Frequency,
    MacroObservation,
    MarketObservation,
    PriceField,
    ReleaseEvent,
    ReleaseStage,
    ReturnConvention,
    SeasonalAdjustment,
)

FIXTURE_RETRIEVED_AT = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
FIXTURE_ADAPTER_VERSION = "fixture-1"
FIXTURE_SOURCE = "synthetic_fixture"
FIXTURE_TIMEZONE = "America/New_York"

FIXTURE_FILES = {
    "vintage": "vintage_fixture.csv",
    "release_stage": "release_stage_fixture.csv",
    "release_calendar": "release_calendar_fixture.csv",
    "ragged_edge": "ragged_edge_fixture.csv",
    "market_price": "market_price_fixture.csv",
    "consensus": "consensus_template.csv",
    "state_alignment": "state_alignment_fixture.csv",
}


def fixtures_dir(base: Path | str | None = None) -> Path:
    """Directory holding the bundled fixture CSVs (``<project root>/examples``)."""
    if base is not None:
        return Path(base)
    return find_project_root(Path(__file__).resolve().parent) / "examples"


def _rows(name: str, base: Path | str | None) -> list[dict[str, str]]:
    path = fixtures_dir(base) / FIXTURE_FILES[name]
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def parse_reference_period(text: str) -> tuple[date, date, Frequency]:
    """Parse ``YYYY-MM`` (monthly) or ``YYYY-Qn`` (quarterly) reference periods."""
    year_text, _, rest = text.partition("-")
    year = int(year_text)
    if rest.upper().startswith("Q"):
        quarter = int(rest[1:])
        if quarter not in (1, 2, 3, 4):
            raise ValueError(f"bad quarter in {text!r}")
        first = 3 * quarter - 2
        last = first + 2
        return (
            date(year, first, 1),
            date(year, last, calendar.monthrange(year, last)[1]),
            Frequency.QUARTERLY,
        )
    month = int(rest)
    return (
        date(year, month, 1),
        date(year, month, calendar.monthrange(year, month)[1]),
        Frequency.MONTHLY,
    )


def _exact(ts: datetime) -> AvailabilityStamp:
    return AvailabilityStamp(
        available_at=ts,
        precision=AvailabilityPrecision.EXACT_TIMESTAMP,
        availability_source=AvailabilitySource.OFFICIAL_RELEASE_SCHEDULE,
        raw_available_date=ts.date(),
        resolver_version=FIXTURE_ADAPTER_VERSION,
    )


# --- macro ----------------------------------------------------------------------------


def load_vintage_fixture(base: Path | str | None = None) -> list[MacroObservation]:
    """Successive vintages of one monthly series (initial print then a revision)."""
    rows = sorted(
        _rows("vintage", base),
        key=lambda r: (r["series_id"], r["reference_start"], r["available_at"]),
    )
    out: list[MacroObservation] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        start = date.fromisoformat(row["reference_start"])
        end = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
        key = (row["series_id"], row["reference_start"])
        stage = ReleaseStage.REVISION if key in seen else ReleaseStage.INITIAL
        seen.add(key)
        available = datetime.fromisoformat(row["available_at"])
        out.append(
            MacroObservation(
                source=FIXTURE_SOURCE,
                series_id=row["series_id"],
                retrieved_at=FIXTURE_RETRIEVED_AT,
                source_snapshot_id="fixture_vintage",
                adapter_version=FIXTURE_ADAPTER_VERSION,
                release_stage=stage,
                reference_start=start,
                reference_end=end,
                value=float(row["value"]),
                units="index",
                frequency=Frequency.MONTHLY,
                seasonal_adjustment=SeasonalAdjustment.SEASONALLY_ADJUSTED,
                release_timestamp=available,
                availability=_exact(available),
                vintage_date=date.fromisoformat(row["vintage_date"]),
                realtime_start=date.fromisoformat(row["realtime_start"]),
                realtime_end=date.fromisoformat(row["realtime_end"]),
            )
        )
    return out


def load_release_stage_fixture(base: Path | str | None = None) -> list[MacroObservation]:
    """Successive estimate rounds (advance/second/third) of one quarterly release."""
    out: list[MacroObservation] = []
    for row in _rows("release_stage", base):
        start, end, freq = parse_reference_period(row["reference_period"])
        released = datetime.fromisoformat(row["released_at"])
        out.append(
            MacroObservation(
                source=FIXTURE_SOURCE,
                series_id=f"{row['release_family']}_LEVEL",
                retrieved_at=FIXTURE_RETRIEVED_AT,
                source_snapshot_id="fixture_release_stage",
                adapter_version=FIXTURE_ADAPTER_VERSION,
                release_family=row["release_family"],
                release_id=f"{row['release_family']}-{row['reference_period']}-{row['release_stage']}",
                release_stage=ReleaseStage(row["release_stage"]),
                reference_start=start,
                reference_end=end,
                value=float(row["value"]),
                units="index",
                frequency=freq,
                seasonal_adjustment=SeasonalAdjustment.SEASONALLY_ADJUSTED_ANNUAL_RATE,
                release_timestamp=released,
                availability=_exact(released),
            )
        )
    return out


def load_release_calendar_fixture(base: Path | str | None = None) -> list[ReleaseEvent]:
    out: list[ReleaseEvent] = []
    for row in _rows("release_calendar", base):
        start, end, _ = parse_reference_period(row["reference_period"])
        actual = row["actual_release_at"].strip()
        out.append(
            ReleaseEvent(
                release_id=f"{row['release_id']}-{row['reference_period']}",
                release_family=row["release_id"],
                release_name=row["release_name"],
                source=FIXTURE_SOURCE,
                calendar_snapshot_id="fixture_release_calendar",
                source_timezone=row["source_timezone"],
                scheduled_at=datetime.fromisoformat(row["scheduled_at"]),
                actual_release_at=datetime.fromisoformat(actual) if actual else None,
                reference_start=start,
                reference_end=end,
                release_stage=ReleaseStage(row["release_stage"]),
            )
        )
    return out


class FixtureFeatureRow(BaseModel):
    """One ragged-edge feature row as of a decision time (fixture schema)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    feature_name: Annotated[str, Field(min_length=1)]
    value: FiniteFloat
    available_at: AwareDatetime
    reference_period: Annotated[str, Field(min_length=1)]
    age_since_available_days: Annotated[int, Field(ge=0)]
    stale: bool


def load_ragged_edge_fixture(base: Path | str | None = None) -> list[FixtureFeatureRow]:
    rows = [
        FixtureFeatureRow(
            as_of=datetime.fromisoformat(r["as_of"]),
            feature_name=r["feature_name"],
            value=float(r["value"]),
            available_at=datetime.fromisoformat(r["available_at"]),
            reference_period=r["reference_period"],
            age_since_available_days=int(r["age_since_available_days"]),
            stale=r["stale"].strip().lower() == "true",
        )
        for r in _rows("ragged_edge", base)
    ]
    for row in rows:
        if row.available_at > row.as_of:
            raise ValueError(f"fixture row {row.feature_name} is not available at its as_of")
    return rows


# --- market / expectations / regimes -------------------------------------------------


def fixture_asset(asset_id: str = "SPY") -> AssetMetadata:
    """Synthetic metadata matching ``market_price_fixture.csv``."""
    return AssetMetadata(
        asset_id=asset_id,
        role="broad_us_equity",
        provider="SYNTHETIC",
        currency="USD",
        timezone=FIXTURE_TIMEZONE,
        first_tradable_date=date(2026, 10, 14),
        coverage_start=date(2026, 10, 14),
        price_adjustment_policy=AdjustmentPolicy.SPLIT_AND_DIVIDEND_ADJUSTED,
        return_convention=ReturnConvention.ADJUSTED_CLOSE_TO_ADJUSTED_CLOSE,
    )


_PRICE_COLUMNS = (
    ("open", "unadjusted"),
    ("close", "unadjusted"),
    ("adjusted_close", "split_and_dividend_adjusted"),
)


def load_market_price_fixture(base: Path | str | None = None) -> list[MarketObservation]:
    out: list[MarketObservation] = []
    for row in _rows("market_price", base):
        ts = datetime.fromisoformat(row["timestamp"])
        for column, policy in _PRICE_COLUMNS:
            out.append(
                MarketObservation(
                    asset_id=row["asset_id"],
                    timestamp=ts,
                    field=PriceField(column),
                    value=float(row[column]),
                    currency="USD",
                    provider=row["provider"],
                    adjustment_policy=AdjustmentPolicy(policy),
                    retrieved_at=FIXTURE_RETRIEVED_AT,
                    snapshot_id="fixture_market_price",
                )
            )
    return out


def load_consensus_fixture(base: Path | str | None = None) -> list[ConsensusExpectation]:
    out: list[ConsensusExpectation] = []
    for row in _rows("consensus", base):
        if row["expectation_type"] != "consensus":
            raise ValueError(f"consensus fixture row has type {row['expectation_type']!r}")
        start, end, _ = parse_reference_period(row["reference_period"])
        available = datetime.fromisoformat(row["available_at"])
        out.append(
            ConsensusExpectation(
                release_id=f"{row['release_id']}-{row['reference_period']}",
                reference_start=start,
                reference_end=end,
                expected_value=float(row["expected_value"]),
                units="percent_mom",
                expectation_source=row["expectation_source"],
                forecast_created_at=datetime.fromisoformat(row["forecast_created_at"]),
                availability=AvailabilityStamp(
                    available_at=available,
                    precision=AvailabilityPrecision.PROVIDER_TIMESTAMP,
                    availability_source=AvailabilitySource.PROVIDER_TIMESTAMP,
                ),
                source_snapshot_id="fixture_consensus",
            )
        )
    return out


class StateDescriptorRow(BaseModel):
    """Raw state centroid of one regime-model fit (fixture schema)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_id: Annotated[str, Field(min_length=1)]
    raw_state_id: Annotated[int, Field(ge=0)]
    growth_factor: FiniteFloat
    inflation_factor: FiniteFloat
    prior_canonical_state: str | None = None


def load_state_alignment_fixture(base: Path | str | None = None) -> list[StateDescriptorRow]:
    return [
        StateDescriptorRow(
            fit_id=r["fit_id"],
            raw_state_id=int(r["raw_state_id"]),
            growth_factor=float(r["growth_factor"]),
            inflation_factor=float(r["inflation_factor"]),
            prior_canonical_state=r["prior_canonical_state"].strip() or None,
        )
        for r in _rows("state_alignment", base)
    ]


# --- helpers ------------------------------------------------------------------------------


def known_at(
    observations: Iterable[MacroObservation], decision_time: datetime
) -> dict[tuple[str, date], MacroObservation]:
    """Latest-known value per (series, reference_start) at ``decision_time``.

    A deliberately tiny reference implementation for tests; the production
    as-of engine is Task 2.12.
    """
    best: dict[tuple[str, date], MacroObservation] = {}
    for obs in observations:
        if not obs.is_available_at(decision_time):
            continue
        key = (obs.series_id, obs.reference_start)
        current = best.get(key)
        if current is None or obs.availability.available_at > current.availability.available_at:
            best[key] = obs
    return best
