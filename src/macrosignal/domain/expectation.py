"""Expectation observations: consensus, model forecasts and proxies as distinct types.

``docs/EXPECTATIONS_AND_SURPRISES.md`` separates three concepts that must never
be relabelled into one another:

* :class:`ConsensusExpectation` - a real pre-release market/survey consensus,
  the only input that may produce a *market surprise*;
* :class:`ModelForecast` - a model's forecast created before the release, which
  produces a *forecast error*;
* :class:`ProxyExpectation` - an explicitly declared proxy (e.g. prior print),
  which produces a *proxy surprise*.

Every expectation records when it was created and when it became available
(an :class:`AvailabilityStamp`) plus its source/model provenance.
:func:`check_pre_release` enforces the per-mode chronology: an expectation that
becomes available at or after the target release is rejected.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    TypeAdapter,
    model_validator,
)

from macrosignal.domain.availability import AvailabilityStamp
from macrosignal.domain.release_event import ReleaseEvent

NonEmptyStr = Annotated[str, Field(min_length=1)]


class ExpectationType(StrEnum):
    CONSENSUS = "consensus"
    MODEL_FORECAST = "model_forecast"
    PROXY = "proxy"


class SurpriseMode(StrEnum):
    """Which comparison a research run performs; each accepts one expectation type."""

    MARKET_SURPRISE = "market_surprise"
    FORECAST_ERROR = "forecast_error"
    PROXY_SURPRISE = "proxy_surprise"


_MODE_TYPE: dict[SurpriseMode, ExpectationType] = {
    SurpriseMode.MARKET_SURPRISE: ExpectationType.CONSENSUS,
    SurpriseMode.FORECAST_ERROR: ExpectationType.MODEL_FORECAST,
    SurpriseMode.PROXY_SURPRISE: ExpectationType.PROXY,
}


class _ExpectationBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: NonEmptyStr
    reference_start: date
    reference_end: date
    expected_value: FiniteFloat
    units: NonEmptyStr
    expectation_source: NonEmptyStr
    forecast_created_at: AwareDatetime
    availability: AvailabilityStamp
    source_snapshot_id: NonEmptyStr

    @model_validator(mode="after")
    def _check_base_chronology(self) -> _ExpectationBase:
        problems: list[str] = []
        if self.reference_end < self.reference_start:
            problems.append("reference_end is before reference_start")
        if self.availability.available_at < self.forecast_created_at:
            problems.append(
                "availability.available_at precedes forecast_created_at; an expectation "
                "cannot be known before it was created"
            )
        problems.extend(self._extra_problems())
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _extra_problems(self) -> list[str]:
        return []

    def is_available_at(self, decision_time: datetime) -> bool:
        return self.availability.is_available_at(decision_time)


class ConsensusExpectation(_ExpectationBase):
    """A timestamped pre-release consensus from a named provider/survey."""

    expectation_type: Literal[ExpectationType.CONSENSUS] = ExpectationType.CONSENSUS
    respondent_count: Annotated[int, Field(ge=1)] | None = None


class ModelForecast(_ExpectationBase):
    """A model forecast with its model identity and training cutoff."""

    expectation_type: Literal[ExpectationType.MODEL_FORECAST] = ExpectationType.MODEL_FORECAST
    model_id: NonEmptyStr
    model_version: NonEmptyStr
    training_cutoff: AwareDatetime
    input_snapshot_ids: tuple[NonEmptyStr, ...] = ()

    def _extra_problems(self) -> list[str]:
        if self.training_cutoff > self.forecast_created_at:
            return ["training_cutoff is after forecast_created_at"]
        return []


class ProxyExpectation(_ExpectationBase):
    """An explicitly declared proxy expectation (e.g. previous print, random walk)."""

    expectation_type: Literal[ExpectationType.PROXY] = ExpectationType.PROXY
    proxy_method: NonEmptyStr


Expectation = Annotated[
    ConsensusExpectation | ModelForecast | ProxyExpectation,
    Field(discriminator="expectation_type"),
]

_EXPECTATION_ADAPTER: TypeAdapter[ConsensusExpectation | ModelForecast | ProxyExpectation] = (
    TypeAdapter(Expectation)
)


def parse_expectation(data: object) -> ConsensusExpectation | ModelForecast | ProxyExpectation:
    """Validate a mapping into the concrete expectation type named by ``expectation_type``."""
    return _EXPECTATION_ADAPTER.validate_python(data)


class ExpectationChronologyError(ValueError):
    """An expectation is not usable for the requested surprise mode/release."""


def check_pre_release(
    expectation: ConsensusExpectation | ModelForecast | ProxyExpectation,
    release: ReleaseEvent | datetime,
    mode: SurpriseMode,
) -> None:
    """Raise :class:`ExpectationChronologyError` unless ``expectation`` is valid for ``mode``.

    Rules:

    * the expectation type must match the mode (no relabelling a model forecast
      as a market surprise);
    * the expectation must be available strictly before the target release;
    * a model forecast's training cutoff must be strictly before the release;
    * when a :class:`ReleaseEvent` is given, release id and reference period must
      match and the event must have an *actual* release time.
    """
    expected_type = _MODE_TYPE[mode]
    if expectation.expectation_type is not expected_type:
        raise ExpectationChronologyError(
            f"{mode.value} requires a {expected_type.value} expectation, got "
            f"{expectation.expectation_type.value}"
        )

    if isinstance(release, ReleaseEvent):
        if release.release_id != expectation.release_id:
            raise ExpectationChronologyError(
                f"expectation release_id {expectation.release_id!r} does not match release "
                f"{release.release_id!r}"
            )
        if (release.reference_start, release.reference_end) != (
            expectation.reference_start,
            expectation.reference_end,
        ):
            raise ExpectationChronologyError("expectation reference period does not match release")
        if release.actual_release_at is None:
            raise ExpectationChronologyError(
                f"release {release.release_id!r} has no actual_release_at; cannot verify the "
                "expectation was pre-release"
            )
        release_at = release.actual_release_at
    else:
        if release.tzinfo is None or release.utcoffset() is None:
            raise ExpectationChronologyError("release time must be timezone-aware")
        release_at = release

    if expectation.availability.available_at >= release_at:
        raise ExpectationChronologyError(
            f"expectation available at {expectation.availability.available_at.isoformat()} is "
            f"not before the release at {release_at.isoformat()}"
        )
    if isinstance(expectation, ModelForecast) and expectation.training_cutoff >= release_at:
        raise ExpectationChronologyError(
            "model forecast training_cutoff is not before the target release"
        )
