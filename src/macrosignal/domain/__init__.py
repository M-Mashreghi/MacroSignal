"""Canonical, immutable domain models shared across MacroSignal layers."""

from macrosignal.domain.availability import AvailabilityPrecision, AvailabilityStamp
from macrosignal.domain.macro_observation import (
    Frequency,
    MacroObservation,
    ReleaseStage,
    SeasonalAdjustment,
)

__all__ = [
    "AvailabilityPrecision",
    "AvailabilityStamp",
    "Frequency",
    "MacroObservation",
    "ReleaseStage",
    "SeasonalAdjustment",
]
