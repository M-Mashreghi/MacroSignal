"""Market observations and asset lifecycle metadata.

``AssetMetadata`` records everything a return/backtest engine must know about an
instrument before it may use a price: provider, currency, exchange timezone,
adjustment policy, return convention and - crucially - the tradable lifecycle
(first/last tradable date) and provider coverage window.  Coverage may never
start before the instrument was tradable, so an ETF cannot be backfilled before
its inception (docs/RETURN_AND_EXECUTION_CONTRACT.md).

``MarketObservation`` is one provider value (open, close, adjusted close, ...)
of one asset at one timezone-aware timestamp, with its adjustment policy and
snapshot provenance stored explicitly.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    field_validator,
    model_validator,
)

from macrosignal.domain.timezones import validate_iana_timezone

NonEmptyStr = Annotated[str, Field(min_length=1)]
AssetId = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9._-]*$")]
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class PriceField(StrEnum):
    """Which provider field a market value represents."""

    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    ADJUSTED_CLOSE = "adjusted_close"
    TOTAL_RETURN_INDEX = "total_return_index"
    VOLUME = "volume"


class AdjustmentPolicy(StrEnum):
    """Corporate-action adjustment applied by the provider to a value."""

    UNADJUSTED = "unadjusted"
    SPLIT_ADJUSTED = "split_adjusted"
    SPLIT_AND_DIVIDEND_ADJUSTED = "split_and_dividend_adjusted"
    TOTAL_RETURN = "total_return"


class ReturnConvention(StrEnum):
    """How research returns are computed for an asset."""

    ADJUSTED_CLOSE_TO_ADJUSTED_CLOSE = "adjusted_close_to_adjusted_close"
    TOTAL_RETURN_INDEX = "total_return_index"
    CLOSE_TO_CLOSE_PRICE_ONLY = "close_to_close_price_only"


#: Adjustment policies a provider field can legitimately carry.
FIELD_ADJUSTMENTS: dict[PriceField, frozenset[AdjustmentPolicy]] = {
    **{
        f: frozenset({AdjustmentPolicy.UNADJUSTED, AdjustmentPolicy.SPLIT_ADJUSTED})
        for f in (PriceField.OPEN, PriceField.HIGH, PriceField.LOW, PriceField.CLOSE)
    },
    PriceField.ADJUSTED_CLOSE: frozenset(
        {AdjustmentPolicy.SPLIT_ADJUSTED, AdjustmentPolicy.SPLIT_AND_DIVIDEND_ADJUSTED}
    ),
    PriceField.TOTAL_RETURN_INDEX: frozenset({AdjustmentPolicy.TOTAL_RETURN}),
    PriceField.VOLUME: frozenset({AdjustmentPolicy.UNADJUSTED, AdjustmentPolicy.SPLIT_ADJUSTED}),
}


class MarketObservation(BaseModel):
    """One provider value for one asset at one timestamp."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: AssetId
    timestamp: AwareDatetime
    field: PriceField
    value: FiniteFloat
    currency: CurrencyCode
    provider: NonEmptyStr
    adjustment_policy: AdjustmentPolicy
    retrieved_at: AwareDatetime
    snapshot_id: NonEmptyStr

    @model_validator(mode="after")
    def _check(self) -> MarketObservation:
        problems: list[str] = []
        if self.field is PriceField.VOLUME:
            if self.value < 0:
                problems.append("volume must be non-negative")
        elif self.value <= 0:
            problems.append(f"{self.field.value} price must be positive")
        if self.adjustment_policy not in FIELD_ADJUSTMENTS[self.field]:
            problems.append(
                f"field {self.field.value!r} cannot carry adjustment policy "
                f"{self.adjustment_policy.value!r}"
            )
        if self.retrieved_at < self.timestamp:
            problems.append("retrieved_at precedes the observation timestamp")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class LifecycleError(ValueError):
    """A market observation falls outside an asset's tradable lifecycle/coverage."""


class AssetMetadata(BaseModel):
    """Instrument identity, conventions, tradable lifecycle and provider coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: AssetId
    role: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    provider: NonEmptyStr
    currency: CurrencyCode
    timezone: NonEmptyStr
    first_tradable_date: date
    last_tradable_date: date | None = None
    coverage_start: date
    coverage_end: date | None = None
    price_adjustment_policy: AdjustmentPolicy
    return_convention: ReturnConvention

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        return validate_iana_timezone(value, field="timezone")

    @model_validator(mode="after")
    def _check_lifecycle(self) -> AssetMetadata:
        problems: list[str] = []
        if (
            self.last_tradable_date is not None
            and self.last_tradable_date < self.first_tradable_date
        ):
            problems.append("last_tradable_date is before first_tradable_date")
        if self.coverage_start < self.first_tradable_date:
            problems.append(
                f"coverage_start {self.coverage_start} is before first_tradable_date "
                f"{self.first_tradable_date}; do not backfill before inception"
            )
        if self.coverage_end is not None:
            if self.coverage_end < self.coverage_start:
                problems.append("coverage_end is before coverage_start")
            if self.last_tradable_date is not None and self.coverage_end > self.last_tradable_date:
                problems.append("coverage_end is after last_tradable_date")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def local_date(self, ts: datetime) -> date:
        """Trading-session date of ``ts`` in the asset's exchange timezone."""
        return ts.astimezone(self.zone).date()

    def is_tradable_on(self, day: date) -> bool:
        if day < self.first_tradable_date:
            return False
        return self.last_tradable_date is None or day <= self.last_tradable_date

    def is_covered_on(self, day: date) -> bool:
        if not self.is_tradable_on(day) or day < self.coverage_start:
            return False
        return self.coverage_end is None or day <= self.coverage_end

    def check_observation(self, obs: MarketObservation) -> None:
        """Raise :class:`LifecycleError` unless ``obs`` is consistent with this asset."""
        problems: list[str] = []
        if obs.asset_id != self.asset_id:
            problems.append(f"asset_id {obs.asset_id!r} != {self.asset_id!r}")
        if obs.provider != self.provider:
            problems.append(f"provider {obs.provider!r} != {self.provider!r}")
        if obs.currency != self.currency:
            problems.append(f"currency {obs.currency!r} != {self.currency!r}")
        day = self.local_date(obs.timestamp)
        if not self.is_tradable_on(day):
            problems.append(f"{day} is outside the tradable lifecycle of {self.asset_id}")
        elif not self.is_covered_on(day):
            problems.append(f"{day} is outside provider coverage of {self.asset_id}")
        if problems:
            raise LifecycleError("; ".join(problems))
