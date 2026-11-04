"""Research return engine & corporate-action semantics (Task 5.2)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import AssetMetadata, MarketObservation, ResearchReturnSpec
from macrosignal.portfolio.returns import ReturnSemanticsError, compute_returns

CAL = UsTradingCalendar()
SPEC = ResearchReturnSpec(
    convention="adjusted_close_to_adjusted_close",
    price_field="adjusted_close",
    adjustment_policy="split_and_dividend_adjusted",
)
ASSET = AssetMetadata(
    asset_id="SPY",
    role="broad_us_equity",
    provider="SYN",
    currency="USD",
    timezone="America/New_York",
    first_tradable_date=date(2026, 11, 2),
    coverage_start=date(2026, 11, 2),
    price_adjustment_policy="split_and_dividend_adjusted",
    return_convention="adjusted_close_to_adjusted_close",
)
SESSIONS = CAL.sessions(date(2026, 11, 2), date(2026, 11, 30))


def _obs(day: date, value: float, **kw: object) -> MarketObservation:
    data = {
        "asset_id": "SPY",
        "timestamp": CAL.session_close(day),
        "field": "adjusted_close",
        "value": value,
        "currency": "USD",
        "provider": "SYN",
        "adjustment_policy": "split_and_dividend_adjusted",
        "retrieved_at": datetime(2026, 12, 31, tzinfo=UTC),
        "snapshot_id": "raw",
    }
    data.update(kw)
    return MarketObservation.model_validate(data)


def _prices(
    skip: tuple[date, ...] = (), override: dict[date, float] | None = None
) -> list[MarketObservation]:
    vals = {d: 100.0 * (1.001**i) for i, d in enumerate(SESSIONS)}
    vals.update(override or {})
    return [_obs(d, v) for d, v in vals.items() if d not in skip]


def test_session_returns_including_early_close() -> None:
    s = compute_returns(ASSET, _prices(), SPEC, CAL, date(2026, 11, 1), date(2026, 11, 30))
    r = s.as_dict()
    assert len(r) == len(SESSIONS) - 1 and s.missing_sessions == ()
    assert r[date(2026, 11, 3)] == pytest.approx(0.001)
    assert date(2026, 11, 27) in r  # early-close session priced at 13:00
    assert next(x for x in s.returns if x.session == date(2026, 11, 27)).previous_session == date(
        2026, 11, 25
    )


def test_missing_session_is_not_bridged() -> None:
    s = compute_returns(
        ASSET, _prices(skip=(date(2026, 11, 10),)), SPEC, CAL, date(2026, 11, 2), date(2026, 11, 30)
    )
    assert s.missing_sessions == (date(2026, 11, 10),)
    r = s.as_dict()
    assert date(2026, 11, 10) not in r and date(2026, 11, 11) not in r


def test_suspicious_move_flagged_or_rejected() -> None:
    split_like = _prices(override={date(2026, 11, 16): 50.0})
    s = compute_returns(ASSET, split_like, SPEC, CAL, date(2026, 11, 2), date(2026, 11, 30))
    assert s.suspicious_moves == (date(2026, 11, 16), date(2026, 11, 17))
    with pytest.raises(ReturnSemanticsError, match="corporate action"):
        compute_returns(
            ASSET,
            split_like,
            SPEC,
            CAL,
            date(2026, 11, 2),
            date(2026, 11, 30),
            reject_suspicious=True,
        )


def test_semantics_mismatches_rejected() -> None:
    raw = [_obs(SESSIONS[0], 100.0, field="close", adjustment_policy="unadjusted")]
    with pytest.raises(ReturnSemanticsError, match="does not match"):
        compute_returns(ASSET, raw, SPEC, CAL, SESSIONS[0], SESSIONS[-1])
    wrong_conv = AssetMetadata.model_validate(
        {**ASSET.model_dump(), "return_convention": "total_return_index"}
    )
    with pytest.raises(ReturnSemanticsError, match="declares"):
        compute_returns(wrong_conv, _prices(), SPEC, CAL, SESSIONS[0], SESSIONS[-1])
    off = [_obs(SESSIONS[0], 1.0, timestamp=datetime(2026, 11, 2, 12, tzinfo=UTC))]
    with pytest.raises(ReturnSemanticsError, match="session close"):
        compute_returns(ASSET, off, SPEC, CAL, SESSIONS[0], SESSIONS[-1])


def test_lifecycle_limits_sessions() -> None:
    s = compute_returns(ASSET, _prices(), SPEC, CAL, date(2026, 10, 1), date(2026, 11, 30))
    assert min(x.previous_session for x in s.returns) == date(2026, 11, 2)
    assert s.missing_sessions == ()
