"""Rule-based macro quadrants (Task 4.1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from macrosignal.features.frame import AsOfFeatureFrame, PanelCell, SourceKind
from macrosignal.regimes.quadrants import (
    Quadrant,
    QuadrantRule,
    QuadrantStatus,
    classify,
    classify_frame,
)

NY = ZoneInfo("America/New_York")
T0 = datetime(2026, 1, 5, 9, 0, tzinfo=NY)
G, INF = "growth__yoy", "inflation__yoy"


def _cell(t: datetime, name: str, value: float, stale: bool = False) -> PanelCell:
    avail = t - timedelta(days=3)
    return PanelCell(
        as_of=t,
        feature_name=name,
        kind=SourceKind.MACRO,
        value=value,
        available_at=avail,
        availability_precision="exact_timestamp",
        age_since_available=t - avail,
        stale=stale,
    )


def _frame(
    pairs: list[tuple[float | None, float | None]], stale_at: int | None = None
) -> AsOfFeatureFrame:
    times, cells = [], []
    for k, (g, i) in enumerate(pairs):
        t = T0 + timedelta(days=7 * k)
        times.append(t)
        if g is not None:
            cells.append(_cell(t, G, g, stale=k == stale_at))
        if i is not None:
            cells.append(_cell(t, INF, i))
    return AsOfFeatureFrame(decision_times=tuple(times), cells=tuple(cells), missing={})


def test_classification_table() -> None:
    assert classify(1, -1, 0, 0) is Quadrant.GROWTH_DISINFLATION
    assert classify(1, 1, 0, 0) is Quadrant.GROWTH_INFLATION
    assert classify(-1, 1, 0, 0) is Quadrant.SLOWDOWN_INFLATION
    assert classify(-1, -1, 0, 0) is Quadrant.SLOWDOWN_DISINFLATION


def test_fixed_thresholds_with_contributions() -> None:
    rule = QuadrantRule(
        growth_feature=G,
        inflation_feature=INF,
        threshold_method="fixed",
        growth_threshold=2.0,
        inflation_threshold=2.5,
    )
    (s,) = classify_frame(_frame([(2.4, 3.1)]), rule)
    assert s.label is Quadrant.GROWTH_INFLATION and s.status is QuadrantStatus.OK
    assert (s.growth_value, s.inflation_value) == (2.4, 3.1)
    assert (s.growth_threshold, s.inflation_threshold) == (2.0, 2.5)
    assert s.growth_available_at == T0 - timedelta(days=3)


def test_statistical_thresholds_use_only_prior_times() -> None:
    rule = QuadrantRule(
        growth_feature=G, inflation_feature=INF, threshold_method="expanding_median", min_history=3
    )
    pairs = [(1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (2.5, 2.5), (10.0, 10.0)]
    states = classify_frame(_frame(pairs), rule)
    assert [s.status for s in states[:3]] == [QuadrantStatus.INSUFFICIENT_HISTORY] * 3
    assert states[3].growth_threshold == 2.0 and states[3].inflation_threshold == 3.0
    assert states[3].label is Quadrant.GROWTH_DISINFLATION
    # A later extreme value cannot change an earlier state's thresholds.
    earlier = classify_frame(_frame(pairs[:4]), rule)
    assert earlier[3] == states[3]
    mean_rule = rule.model_copy(update={"threshold_method": "expanding_mean"})
    assert classify_frame(_frame(pairs), mean_rule)[4].growth_threshold == pytest.approx(2.125)


def test_missing_and_stale_inputs_give_no_label() -> None:
    rule = QuadrantRule(
        growth_feature=G,
        inflation_feature=INF,
        threshold_method="fixed",
        growth_threshold=0,
        inflation_threshold=0,
    )
    states = classify_frame(_frame([(None, 1.0), (1.0, 1.0)], stale_at=1), rule)
    assert states[0].status is QuadrantStatus.MISSING_INPUT and states[0].label is None
    assert states[1].status is QuadrantStatus.STALE_INPUT and states[1].label is None
    lenient = rule.model_copy(update={"allow_stale": True})
    assert (
        classify_frame(_frame([(1.0, 1.0)], stale_at=0), lenient)[0].label
        is Quadrant.GROWTH_INFLATION
    )


def test_rule_validation() -> None:
    with pytest.raises(ValidationError, match="require growth_threshold"):
        QuadrantRule(growth_feature=G, inflation_feature=INF, threshold_method="fixed")
    with pytest.raises(ValidationError, match="must not declare"):
        QuadrantRule(
            growth_feature=G,
            inflation_feature=INF,
            threshold_method="expanding_median",
            growth_threshold=1.0,
        )
