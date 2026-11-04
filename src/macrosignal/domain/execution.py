"""Return, execution-price, cash-return and timing contracts.

Implements the typed side of ``docs/RETURN_AND_EXECUTION_CONTRACT.md``:

* :class:`ResearchReturnSpec` - one return convention with the price field and
  corporate-action adjustment it needs;
* :class:`ExecutionPriceSpec` - the tradable field fills are priced at;
* :class:`ExecutionPreset` / :data:`EXECUTION_PRESETS` - named daily presets
  (``next_session_close``, ``next_session_open``, ``same_day_close``);
* :class:`CashReturnSpec` / :class:`RiskFreeSpec` - explicit cash and Sharpe
  risk-free assumptions;
* :class:`ReturnExecutionContract` - the combination a backtest declares, which
  rejects incompatible price/adjustment combinations;
* :class:`DecisionTimeline` - separate information, signal, decision,
  execution and mark timestamps, with the availability gate.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from macrosignal.domain.availability import AvailabilityStamp
from macrosignal.domain.market import AdjustmentPolicy, PriceField, ReturnConvention

NonEmptyStr = Annotated[str, Field(min_length=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- research returns ----------------------------------------------------------

#: The (field, adjustment) pairs each research return convention accepts.  Price-only
#: close-to-close must at least be split adjusted to avoid split artifacts.
RETURN_CONVENTION_INPUTS: dict[ReturnConvention, frozenset[tuple[PriceField, AdjustmentPolicy]]] = {
    ReturnConvention.ADJUSTED_CLOSE_TO_ADJUSTED_CLOSE: frozenset(
        {(PriceField.ADJUSTED_CLOSE, AdjustmentPolicy.SPLIT_AND_DIVIDEND_ADJUSTED)}
    ),
    ReturnConvention.TOTAL_RETURN_INDEX: frozenset(
        {(PriceField.TOTAL_RETURN_INDEX, AdjustmentPolicy.TOTAL_RETURN)}
    ),
    ReturnConvention.CLOSE_TO_CLOSE_PRICE_ONLY: frozenset(
        {
            (PriceField.CLOSE, AdjustmentPolicy.SPLIT_ADJUSTED),
            (PriceField.ADJUSTED_CLOSE, AdjustmentPolicy.SPLIT_ADJUSTED),
        }
    ),
}

_DIVIDEND_INCLUSIVE = frozenset(
    {AdjustmentPolicy.SPLIT_AND_DIVIDEND_ADJUSTED, AdjustmentPolicy.TOTAL_RETURN}
)


class ResearchReturnSpec(_Strict):
    convention: ReturnConvention
    price_field: PriceField
    adjustment_policy: AdjustmentPolicy

    @model_validator(mode="after")
    def _check(self) -> ResearchReturnSpec:
        allowed = RETURN_CONVENTION_INPUTS[self.convention]
        if (self.price_field, self.adjustment_policy) not in allowed:
            pairs = sorted(f"{f.value}/{a.value}" for f, a in allowed)
            raise ValueError(
                f"return convention {self.convention.value!r} is incompatible with "
                f"{self.price_field.value}/{self.adjustment_policy.value}; expected one of {pairs}"
            )
        return self

    @property
    def includes_dividends(self) -> bool:
        return self.adjustment_policy in _DIVIDEND_INCLUSIVE


# --- execution prices / presets --------------------------------------------------

_TRADABLE_FIELDS = frozenset({PriceField.OPEN, PriceField.CLOSE})
_TRADABLE_ADJUSTMENTS = frozenset({AdjustmentPolicy.UNADJUSTED, AdjustmentPolicy.SPLIT_ADJUSTED})


class ExecutionPriceSpec(_Strict):
    """A price a fill could actually have happened at (raw or split-adjusted open/close)."""

    field: PriceField
    adjustment_policy: AdjustmentPolicy

    @model_validator(mode="after")
    def _check(self) -> ExecutionPriceSpec:
        problems: list[str] = []
        if self.field not in _TRADABLE_FIELDS:
            problems.append(
                f"{self.field.value!r} is not a tradable execution field; use open or close"
            )
        if self.adjustment_policy not in _TRADABLE_ADJUSTMENTS:
            problems.append(
                f"execution prices cannot be {self.adjustment_policy.value!r}; dividend-adjusted "
                "values were never traded"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self


class ExecutionPresetName(StrEnum):
    NEXT_SESSION_CLOSE = "next_session_close"
    NEXT_SESSION_OPEN = "next_session_open"
    SAME_DAY_CLOSE = "same_day_close"


class ExecutionPreset(_Strict):
    """A named daily timing rule: which session and field a decision is filled at."""

    name: ExecutionPresetName
    execution_field: Literal[PriceField.OPEN, PriceField.CLOSE]
    #: Sessions between the signal session and the execution session.
    session_offset: Annotated[int, Field(ge=0, le=1)]
    #: The signal must be formed strictly before this event of the execution session.
    signal_before: Literal["open", "close"]
    description: NonEmptyStr


EXECUTION_PRESETS: dict[ExecutionPresetName, ExecutionPreset] = {
    ExecutionPresetName.NEXT_SESSION_CLOSE: ExecutionPreset(
        name=ExecutionPresetName.NEXT_SESSION_CLOSE,
        execution_field=PriceField.CLOSE,
        session_offset=1,
        signal_before="close",
        description="Signal on session t, fill at the close of session t+1.",
    ),
    ExecutionPresetName.NEXT_SESSION_OPEN: ExecutionPreset(
        name=ExecutionPresetName.NEXT_SESSION_OPEN,
        execution_field=PriceField.OPEN,
        session_offset=1,
        signal_before="open",
        description=(
            "Signal formed before the next session opens, fill at its open; requires "
            "documented provider open-price semantics."
        ),
    ),
    ExecutionPresetName.SAME_DAY_CLOSE: ExecutionPreset(
        name=ExecutionPresetName.SAME_DAY_CLOSE,
        execution_field=PriceField.CLOSE,
        session_offset=0,
        signal_before="close",
        description="Signal formed before the close of session t, fill at that close.",
    ),
}


def get_execution_preset(name: str | ExecutionPresetName) -> ExecutionPreset:
    try:
        return EXECUTION_PRESETS[ExecutionPresetName(name)]
    except ValueError as exc:
        raise ValueError(f"unknown execution preset {name!r}") from exc


# --- cash / risk-free --------------------------------------------------------------


class CashReturnMode(StrEnum):
    ZERO = "zero"
    PROXY = "proxy"


class CashReturnSpec(_Strict):
    """Explicit return earned by uninvested capital."""

    mode: CashReturnMode
    proxy_series_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _check(self) -> CashReturnSpec:
        if self.mode is CashReturnMode.PROXY and self.proxy_series_id is None:
            raise ValueError("cash mode 'proxy' requires proxy_series_id")
        if self.mode is CashReturnMode.ZERO and self.proxy_series_id is not None:
            raise ValueError("cash mode 'zero' must not declare proxy_series_id")
        return self


class RiskFreeMode(StrEnum):
    ZERO = "zero"
    TREASURY_BILL_PROXY = "treasury_bill_proxy"
    DOCUMENTED_SERIES = "documented_series"


class RiskFreeSpec(_Strict):
    """Which risk-free rate Sharpe-type metrics subtract."""

    mode: RiskFreeMode
    series_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _check(self) -> RiskFreeSpec:
        needs_series = self.mode is not RiskFreeMode.ZERO
        if needs_series and self.series_id is None:
            raise ValueError(f"risk-free mode {self.mode.value!r} requires series_id")
        if not needs_series and self.series_id is not None:
            raise ValueError("risk-free mode 'zero' must not declare series_id")
        return self


# --- full contract --------------------------------------------------------------------


class ReconciliationPolicy(StrEnum):
    """How dividend-inclusive research returns relate to raw execution prices."""

    #: Research and execution use the same price basis; nothing to reconcile.
    NONE = "none"
    #: Returns come from the research series; raw fill prices only time fills and costs.
    RESEARCH_RETURNS_RAW_FILLS_FOR_TIMING_AND_COSTS = (
        "research_returns_raw_fills_for_timing_and_costs"
    )


class ReturnExecutionContract(_Strict):
    """Everything a backtest must declare about returns, fills, cash and risk-free."""

    research_return: ResearchReturnSpec
    execution_price: ExecutionPriceSpec
    preset: ExecutionPreset
    cash: CashReturnSpec
    risk_free: RiskFreeSpec
    reconciliation: ReconciliationPolicy = ReconciliationPolicy.NONE

    @model_validator(mode="after")
    def _check(self) -> ReturnExecutionContract:
        problems: list[str] = []
        if self.execution_price.field is not self.preset.execution_field:
            problems.append(
                f"preset {self.preset.name.value!r} fills at {self.preset.execution_field.value} "
                f"but execution_price.field is {self.execution_price.field.value}"
            )
        mixed = self.research_return.includes_dividends
        if mixed and self.reconciliation is ReconciliationPolicy.NONE:
            problems.append(
                "dividend-inclusive research returns with raw/split-adjusted execution prices "
                "require an explicit reconciliation policy"
            )
        if not mixed and self.reconciliation is not ReconciliationPolicy.NONE:
            problems.append(
                "reconciliation is only meaningful for dividend-inclusive research returns"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self


# --- timing -------------------------------------------------------------------------


class AvailabilityViolation(ValueError):
    """An input was not available at the simulated decision time."""


class DecisionTimeline(_Strict):
    """Separate information, signal, decision, execution and mark timestamps."""

    information_time: AwareDatetime
    signal_time: AwareDatetime
    decision_time: AwareDatetime
    execution_time: AwareDatetime
    mark_time: AwareDatetime

    @model_validator(mode="after")
    def _check_order(self) -> DecisionTimeline:
        problems: list[str] = []
        if self.signal_time < self.information_time:
            problems.append("signal_time precedes information_time")
        if self.decision_time < self.signal_time:
            problems.append("decision_time precedes signal_time")
        if self.execution_time <= self.decision_time:
            problems.append(
                "execution_time must be strictly after decision_time (no same-instant fill)"
            )
        if self.mark_time < self.execution_time:
            problems.append("mark_time precedes execution_time")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def check_inputs(self, stamps: Iterable[AvailabilityStamp]) -> None:
        """Apply the PIT gate: ``max(available_at) <= information_time <= decision_time``."""
        latest: datetime | None = None
        for stamp in stamps:
            if latest is None or stamp.available_at > latest:
                latest = stamp.available_at
        if latest is None:
            return
        if latest > self.information_time:
            raise AvailabilityViolation(
                f"input available at {latest.isoformat()} is after information_time "
                f"{self.information_time.isoformat()}"
            )
