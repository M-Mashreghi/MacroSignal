"""Typed schemas for committed MacroSignal YAML configuration files.

Every model forbids unknown fields so that a misspelled or unsupported key fails
loudly instead of being silently ignored. Integrity policies that the project
documents as mandatory (filtered-only HMM probabilities for signals, training-only
selection, no backfill before inception, strict PIT) are encoded as literal
``True`` / fixed values rather than free switches.

Secrets and machine-specific settings never belong here; see
:mod:`macrosignal.config.settings`.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    """Immutable base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
WindowName = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_]*$")]
ReleaseFamilyName = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")]
NonEmptyStr = Annotated[str, Field(min_length=1)]
ConfigRef = Annotated[str, Field(min_length=1)]

AvailabilityPrecision = Literal[
    "exact_timestamp",
    "provider_timestamp",
    "release_date_only",
    "inferred_eod",
    "unknown",
]
ExecutionPreset = Literal["next_session_close", "next_session_open", "same_day_close"]


def _require_unique(values: list[str], what: str) -> list[str]:
    duplicates = sorted({v for v in values if values.count(v) > 1})
    if duplicates:
        raise ValueError(f"duplicate {what}: {duplicates}")
    return values


# --- configs/series/*: macro series registry ------------------------------------


class MacroSeriesSpec(StrictModel):
    key: Identifier
    provider: NonEmptyStr
    series_id: NonEmptyStr
    family: Identifier
    release_family: ReleaseFamilyName | None
    transformation_set: list[Identifier] = Field(min_length=1)
    stale_after_days: PositiveInt
    pit_required: bool

    @field_validator("transformation_set")
    @classmethod
    def _unique_transformations(cls, v: list[str]) -> list[str]:
        return _require_unique(v, "transformations")


class MacroSeriesRegistry(StrictModel):
    registry_version: PositiveInt
    series: list[MacroSeriesSpec] = Field(min_length=1)

    @field_validator("series")
    @classmethod
    def _unique_keys(cls, v: list[MacroSeriesSpec]) -> list[MacroSeriesSpec]:
        _require_unique([s.key for s in v], "series keys")
        return v

    @property
    def keys(self) -> list[str]:
        return [s.key for s in self.series]


# --- configs/series/release_map_*: release families -----------------------------


class ReleaseFamilySpec(StrictModel):
    official_source: NonEmptyStr
    source_timezone: NonEmptyStr
    default_precision: AvailabilityPrecision
    series_keys: list[Identifier]

    @field_validator("source_timezone")
    @classmethod
    def _valid_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA timezone {v!r}") from exc
        return v

    @field_validator("series_keys")
    @classmethod
    def _unique_series_keys(cls, v: list[str]) -> list[str]:
        return _require_unique(v, "series keys")


class ReleaseMap(StrictModel):
    version: PositiveInt
    release_families: dict[ReleaseFamilyName, ReleaseFamilySpec] = Field(min_length=1)


# --- configs/assets/*: tradable universe ----------------------------------------


class AssetSpec(StrictModel):
    id: Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9._-]*$")]
    role: Identifier
    lifecycle_policy: Identifier


class ReturnPolicy(StrictModel):
    research_return: Identifier
    require_provider_adjustment_metadata: bool


class AssetCashPolicy(StrictModel):
    mode: Identifier
    default_for_demo: Identifier


class AssetUsagePolicy(StrictModel):
    demo_only: bool
    do_not_backfill_before_inception: Literal[True]


class AssetUniverse(StrictModel):
    universe_version: PositiveInt
    frequency: Literal["daily"]
    assets: list[AssetSpec] = Field(min_length=1)
    return_policy: ReturnPolicy
    cash: AssetCashPolicy
    policy: AssetUsagePolicy

    @field_validator("assets")
    @classmethod
    def _unique_ids(cls, v: list[AssetSpec]) -> list[AssetSpec]:
        _require_unique([a.id for a in v], "asset ids")
        return v


# --- configs/regimes/*: regime models -------------------------------------------


class RegimeSelectionSpec(StrictModel):
    training_only: Literal[True]
    criteria: list[Identifier] = Field(min_length=1)


class RegimeAlignmentSpec(StrictModel):
    enabled: bool


class RuleBasedRegimeSpec(StrictModel):
    enabled: bool


class LatentRegimeSpec(StrictModel):
    enabled: bool
    candidate_states: list[Annotated[int, Field(ge=2)]] = Field(min_length=1)
    selection: RegimeSelectionSpec
    alignment: RegimeAlignmentSpec

    @field_validator("candidate_states")
    @classmethod
    def _unique_states(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError(f"duplicate candidate state counts: {v}")
        return v

    @model_validator(mode="after")
    def _alignment_required(self) -> LatentRegimeSpec:
        if self.enabled and not self.alignment.enabled:
            raise ValueError(
                "latent state alignment must be enabled: raw state ids are arbitrary "
                "across refits (docs/REGIME_STATE_ALIGNMENT.md)"
            )
        return self


class HMMRegimeSpec(LatentRegimeSpec):
    probability_for_signals: Literal["filtered"]
    smoothed_ex_post_only: Literal[True]


class RegimeModels(StrictModel):
    rule_based: RuleBasedRegimeSpec
    gmm: LatentRegimeSpec
    hmm: HMMRegimeSpec


class RegimeConfig(StrictModel):
    version: PositiveInt
    models: RegimeModels


# --- configs/signals/*: signal components ---------------------------------------


class ComponentToggle(StrictModel):
    enabled: bool


class SignalDecaySpec(StrictModel):
    type: Identifier
    default_half_life_days: PositiveFloat
    max_age_days: PositiveInt


class SurpriseComponentSpec(StrictModel):
    enabled: bool
    decay: SignalDecaySpec


class TrendComponentSpec(StrictModel):
    enabled: bool
    lookback_days: PositiveInt


class SignalCombinationSpec(StrictModel):
    method: Identifier
    weights_selected_training_only: Literal[True]


class SignalConfig(StrictModel):
    version: PositiveInt
    regime_component: ComponentToggle
    surprise_component: SurpriseComponentSpec
    trend_component: TrendComponentSpec
    combination: SignalCombinationSpec


# --- configs/research/*: research run configurations ----------------------------


class ExecutionSpec(StrictModel):
    preset: ExecutionPreset


class CashSpec(StrictModel):
    mode: Identifier


class CostSpec(StrictModel):
    base_bps: NonNegativeFloat
    stressed_bps: NonNegativeFloat

    @model_validator(mode="after")
    def _stressed_not_below_base(self) -> CostSpec:
        if self.stressed_bps < self.base_bps:
            raise ValueError("stressed_bps must be >= base_bps")
        return self


class ExpectationsSpec(StrictModel):
    mode: Literal["model_forecast", "consensus"]
    label_output_as: Literal["forecast_error", "market_surprise"]

    @model_validator(mode="after")
    def _label_matches_source(self) -> ExpectationsSpec:
        expected = {"model_forecast": "forecast_error", "consensus": "market_surprise"}
        if self.label_output_as != expected[self.mode]:
            raise ValueError(
                f"expectations.mode={self.mode!r} must be labelled "
                f"{expected[self.mode]!r}; model forecast error is never market surprise "
                "(docs/EXPECTATIONS_AND_SURPRISES.md)"
            )
        return self


class PITSpec(StrictModel):
    strict: Literal[True]
    conservative_unknown_time_policy: AvailabilityPrecision


class RaggedEdgeSpec(StrictModel):
    include_age_features: bool
    enforce_staleness: bool


class ReferencedConfigs(StrictModel):
    """Paths, relative to the project root, of the configs a research run uses."""

    macro_registry: ConfigRef
    release_map: ConfigRef
    asset_universe: ConfigRef
    regime_config: ConfigRef
    signal_config: ConfigRef


class DailyResearchConfig(ReferencedConfigs):
    kind: Literal["daily_research"]
    name: Identifier
    mode: Literal["free_research", "market_surprise"]
    start_date: date
    decision_frequency: Literal["daily"]
    expectations: ExpectationsSpec
    pit: PITSpec
    ragged_edge: RaggedEdgeSpec
    execution: ExecutionSpec
    cash: CashSpec
    costs: CostSpec

    @model_validator(mode="after")
    def _mode_matches_expectations(self) -> DailyResearchConfig:
        required = {"free_research": "model_forecast", "market_surprise": "consensus"}
        if self.expectations.mode != required[self.mode]:
            raise ValueError(
                f"mode={self.mode!r} requires expectations.mode={required[self.mode]!r}"
            )
        return self


class WalkForwardSplitSpec(StrictModel):
    type: Literal["expanding", "rolling"]
    minimum_train_years: PositiveInt
    validation_years: NonNegativeInt
    test_step_months: PositiveInt


class RebalanceSpec(StrictModel):
    frequency: Literal["daily", "weekly", "monthly"]


class PortfolioSpec(StrictModel):
    type: Identifier
    annual_vol_target: PositiveFloat
    max_asset_weight: Annotated[float, Field(gt=0, le=1)]
    max_gross_leverage: PositiveFloat


class WalkForwardIntegritySpec(StrictModel):
    strict_pit: Literal[True]
    require_asset_lifecycle: Literal[True]
    require_filtered_regimes: Literal[True]


class WalkForwardConfig(ReferencedConfigs):
    kind: Literal["walk_forward"]
    name: Identifier
    split: WalkForwardSplitSpec
    rebalance: RebalanceSpec
    portfolio: PortfolioSpec
    execution: ExecutionSpec
    cash: CashSpec
    costs: CostSpec
    integrity: WalkForwardIntegritySpec


class OverlapPolicySpec(StrictModel):
    flag_nearby_events: bool
    exclude_if_required: bool


class EventStudyConfig(StrictModel):
    kind: Literal["event_study"]
    name: Identifier
    release_map: ConfigRef
    release_families: list[ReleaseFamilyName] = Field(min_length=1)
    market_frequency: Literal["daily", "intraday"]
    windows: list[WindowName] = Field(min_length=1)
    group_by: list[Identifier]
    minimum_group_size: PositiveInt
    bootstrap_samples: PositiveInt
    overlap_policy: OverlapPolicySpec

    @field_validator("release_families", "windows", "group_by")
    @classmethod
    def _unique_entries(cls, v: list[str]) -> list[str]:
        return _require_unique(v, "entries")


ResearchConfig = DailyResearchConfig | WalkForwardConfig | EventStudyConfig

RESEARCH_KINDS: dict[str, type[StrictModel]] = {
    "daily_research": DailyResearchConfig,
    "walk_forward": WalkForwardConfig,
    "event_study": EventStudyConfig,
}
