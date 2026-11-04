"""Canonical, immutable domain models shared across MacroSignal layers."""

from macrosignal.domain.availability import (
    DATE_LEVEL_PRECISIONS,
    AvailabilityPrecision,
    AvailabilitySource,
    AvailabilityStamp,
)
from macrosignal.domain.macro_observation import (
    Frequency,
    MacroObservation,
    ReleaseStage,
    SeasonalAdjustment,
)
from macrosignal.domain.release_event import ReleaseEvent

__all__ = [
    "DATE_LEVEL_PRECISIONS",
    "AvailabilityPrecision",
    "AvailabilitySource",
    "AvailabilityStamp",
    "Frequency",
    "MacroObservation",
    "ReleaseEvent",
    "ReleaseStage",
    "SeasonalAdjustment",
]
