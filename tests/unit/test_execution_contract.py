"""Return / execution / cash / timing contracts (Task 1.8)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from macrosignal.config import load_research_config
from macrosignal.domain import (
    EXECUTION_PRESETS,
    AvailabilityStamp,
    AvailabilityViolation,
    CashReturnSpec,
    DecisionTimeline,
    ExecutionPresetName,
    ExecutionPriceSpec,
    PriceField,
    ReconciliationPolicy,
    ResearchReturnSpec,
    ReturnExecutionContract,
    RiskFreeSpec,
    get_execution_preset,
)

NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]


def _research(**kw: Any) -> ResearchReturnSpec:
    data = {
        "convention": "adjusted_close_to_adjusted_close",
        "price_field": "adjusted_close",
        "adjustment_policy": "split_and_dividend_adjusted",
    }
    data.update(kw)
    return ResearchReturnSpec.model_validate(data)


def _contract(**kw: Any) -> ReturnExecutionContract:
    data: dict[str, Any] = {
        "research_return": _research(),
        "execution_price": {"field": "close", "adjustment_policy": "split_adjusted"},
        "preset": EXECUTION_PRESETS[ExecutionPresetName.NEXT_SESSION_CLOSE],
        "cash": {"mode": "zero"},
        "risk_free": {"mode": "zero"},
        "reconciliation": "research_returns_raw_fills_for_timing_and_costs",
    }
    data.update(kw)
    return ReturnExecutionContract.model_validate(data)


def test_valid_contract() -> None:
    c = _contract()
    assert c.research_return.includes_dividends
    assert c.preset.session_offset == 1
    assert ReturnExecutionContract.model_validate_json(c.model_dump_json()) == c


@pytest.mark.parametrize(
    ("convention", "field", "policy"),
    [
        ("adjusted_close_to_adjusted_close", "close", "unadjusted"),
        ("adjusted_close_to_adjusted_close", "adjusted_close", "split_adjusted"),
        ("total_return_index", "adjusted_close", "split_and_dividend_adjusted"),
        ("close_to_close_price_only", "close", "unadjusted"),
    ],
)
def test_incompatible_return_inputs_rejected(convention: str, field: str, policy: str) -> None:
    with pytest.raises(ValidationError, match="incompatible"):
        _research(convention=convention, price_field=field, adjustment_policy=policy)


def test_execution_price_must_be_tradable() -> None:
    with pytest.raises(ValidationError, match="not a tradable execution field"):
        ExecutionPriceSpec(field="adjusted_close", adjustment_policy="split_adjusted")
    with pytest.raises(ValidationError, match="never traded"):
        ExecutionPriceSpec(field="close", adjustment_policy="split_and_dividend_adjusted")


def test_preset_field_must_match_execution_price() -> None:
    with pytest.raises(ValidationError, match="fills at close"):
        _contract(execution_price={"field": "open", "adjustment_policy": "unadjusted"})
    ok = _contract(
        execution_price={"field": "open", "adjustment_policy": "unadjusted"},
        preset=get_execution_preset("next_session_open"),
    )
    assert ok.preset.execution_field is PriceField.OPEN


def test_mixed_basis_requires_reconciliation() -> None:
    with pytest.raises(ValidationError, match="reconciliation policy"):
        _contract(reconciliation="none")
    price_only = _research(
        convention="close_to_close_price_only",
        price_field="close",
        adjustment_policy="split_adjusted",
    )
    assert not price_only.includes_dividends
    _contract(research_return=price_only, reconciliation="none")
    with pytest.raises(ValidationError, match="only meaningful"):
        _contract(research_return=price_only)
    assert ReconciliationPolicy.NONE.value == "none"


def test_cash_and_risk_free_explicit() -> None:
    with pytest.raises(ValidationError, match="proxy_series_id"):
        CashReturnSpec(mode="proxy")
    with pytest.raises(ValidationError, match="must not declare"):
        CashReturnSpec(mode="zero", proxy_series_id="DTB3")
    assert CashReturnSpec(mode="proxy", proxy_series_id="DTB3").proxy_series_id == "DTB3"
    with pytest.raises(ValidationError, match="requires series_id"):
        RiskFreeSpec(mode="treasury_bill_proxy")
    with pytest.raises(ValidationError, match="mode"):
        CashReturnSpec.model_validate({})


def test_presets_cover_configured_names() -> None:
    assert {p.value for p in EXECUTION_PRESETS} == {
        "next_session_close",
        "next_session_open",
        "same_day_close",
    }
    for path in ("configs/research/demo_daily.yaml", "configs/research/walk_forward.yaml"):
        cfg = load_research_config(ROOT / path).config
        name = cfg.execution.preset  # type: ignore[union-attr]
        assert get_execution_preset(name).name.value == name
    with pytest.raises(ValueError, match="unknown execution preset"):
        get_execution_preset("same_bar_close")


def _timeline(**kw: Any) -> DecisionTimeline:
    data = {
        "information_time": datetime(2026, 10, 15, 8, 30, tzinfo=NY),
        "signal_time": datetime(2026, 10, 15, 17, 0, tzinfo=NY),
        "decision_time": datetime(2026, 10, 15, 17, 5, tzinfo=NY),
        "execution_time": datetime(2026, 10, 16, 16, 0, tzinfo=NY),
        "mark_time": datetime(2026, 10, 16, 16, 0, tzinfo=NY),
    }
    data.update(kw)
    return DecisionTimeline.model_validate(data)


def test_timeline_ordering() -> None:
    _timeline()
    with pytest.raises(ValidationError, match="signal_time precedes"):
        _timeline(signal_time=datetime(2026, 10, 15, 8, 0, tzinfo=NY))
    with pytest.raises(ValidationError, match="strictly after decision_time"):
        _timeline(execution_time=datetime(2026, 10, 15, 17, 5, tzinfo=NY))
    with pytest.raises(ValidationError, match="mark_time precedes"):
        _timeline(mark_time=datetime(2026, 10, 16, 15, 0, tzinfo=NY))
    with pytest.raises(ValidationError):
        _timeline(decision_time=datetime(2026, 10, 15, 17, 5))


def test_availability_gate() -> None:
    tl = _timeline()
    ok = AvailabilityStamp(
        available_at=datetime(2026, 10, 15, 8, 30, tzinfo=NY), precision="exact_timestamp"
    )
    tl.check_inputs([ok])
    tl.check_inputs([])
    late = AvailabilityStamp(
        available_at=tl.information_time + timedelta(seconds=1), precision="exact_timestamp"
    )
    with pytest.raises(AvailabilityViolation, match="after information_time"):
        tl.check_inputs([ok, late])
