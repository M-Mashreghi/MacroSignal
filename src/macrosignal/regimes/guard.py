"""Filtered-vs-smoothed probability guard for signal / backtest interfaces.

Signal and backtest code must take regime input as a :class:`LiveRegimeSeries`,
which can only be built from contemporaneous, aligned, non-diagnostic states
(via :func:`~macrosignal.domain.regime.require_live_states`) and checks
chronology (strictly increasing decision times, ``fit_cutoff <= as_of``).

Smoothed (future-informed) probabilities live in :class:`ExPostDiagnostics`,
a separate type with no conversion to the live type; :func:`live_regime_input`
rejects anything else at runtime.

To catch *laundering* - smoothed numbers relabelled as ``filtered`` -
:func:`verify_filtered_against_fit` recomputes the filtered path from the HMM
fit and the point-in-time frame and requires the supplied probabilities to
match.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Callable, Iterable, Sequence
from typing import Any, ParamSpec, TypeVar

from macrosignal.domain.regime import (
    FUTURE_INFORMED,
    LiveStateError,
    ProbabilityType,
    RegimeObservation,
    require_live_states,
)
from macrosignal.features.frame import AsOfFeatureFrame
from macrosignal.regimes.hmm import HmmFit

P = ParamSpec("P")
R = TypeVar("R")


class LiveRegimeSeries:
    """Validated, contemporaneous regime states for signal/backtest use."""

    __slots__ = ("_states",)

    def __init__(self, states: Iterable[RegimeObservation]) -> None:
        checked = require_live_states(states)
        for a, b in zip(checked, checked[1:], strict=False):
            if b.as_of <= a.as_of:
                raise LiveStateError("live regime states must have strictly increasing as_of")
        for s in checked:
            if s.fit_cutoff > s.as_of:
                raise LiveStateError(f"{s.fit_id}: fit cutoff after decision time")
        self._states: tuple[RegimeObservation, ...] = tuple(checked)

    @property
    def states(self) -> tuple[RegimeObservation, ...]:
        return self._states

    def __len__(self) -> int:
        return len(self._states)


class ExPostDiagnostics:
    """Container for future-informed / diagnostic states; never usable as live input."""

    __slots__ = ("_states", "label")

    def __init__(self, states: Iterable[RegimeObservation]) -> None:
        self._states = tuple(states)
        self.label = "ex_post_diagnostic"
        for s in self._states:
            if not s.diagnostic and s.probability_type not in FUTURE_INFORMED:
                raise ValueError(
                    "ExPostDiagnostics holds diagnostic or future-informed states only"
                )

    @property
    def states(self) -> tuple[RegimeObservation, ...]:
        return self._states


def live_regime_input(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator for signal/backtest entry points: the ``regimes`` argument must be live."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        value: Any = kwargs.get("regimes", args[0] if args else None)
        if not isinstance(value, LiveRegimeSeries):
            raise LiveStateError(
                f"{func.__name__} requires a LiveRegimeSeries, got {type(value).__name__}; "
                "smoothed or raw states cannot enter signal/backtest code"
            )
        return func(*args, **kwargs)

    return wrapper


def verify_filtered_against_fit(
    fit: HmmFit,
    frame: AsOfFeatureFrame,
    states: Sequence[RegimeObservation],
    *,
    tolerance: float = 1e-9,
) -> None:
    """Raise :class:`LiveStateError` unless ``states`` equal the fit's recomputed filter."""
    expected = {s.as_of: s.raw_probabilities for s in fit.filtered_states(frame)}
    for s in states:
        if s.fit_id != fit.fit_id:
            continue
        if s.probability_type is not ProbabilityType.FILTERED:
            raise LiveStateError(f"{s.as_of.isoformat()}: expected filtered probabilities")
        ref = expected.get(s.as_of)
        got = s.raw_probabilities or {}
        if (
            ref is None
            or set(ref) != set(got)
            or any(not math.isclose(ref[k], got[k], abs_tol=tolerance) for k in ref)
        ):
            raise LiveStateError(
                f"{s.fit_id} @ {s.as_of.isoformat()}: probabilities do not match the "
                "contemporaneous filter (possible smoothed-probability leakage)"
            )
