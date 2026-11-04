"""Treasury nominal / real yield-curve adapter (Task 2.10)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from macrosignal.data.http import HttpClient, ResponseSchemaError
from macrosignal.data.treasury import (
    CurveType,
    fetch_treasury_curve,
    parse_tenor,
    parse_treasury_csv,
)
from macrosignal.domain import AvailabilityPrecision

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "treasury"
NY = ZoneInfo("America/New_York")
RETRIEVED = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _batch(
    name: str = "nominal.csv", curve: CurveType = CurveType.NOMINAL, text: str | None = None
):  # type: ignore[no-untyped-def]
    body = text if text is not None else (FIX / name).read_text(encoding="utf-8")
    return parse_treasury_csv(body, curve, snapshot_id="raw_treasury_x", retrieved_at=RETRIEVED)


def test_nominal_curve_normalized_by_maturity() -> None:
    batch = _batch()
    curve = batch.curve_on(date(2026, 10, 16))
    assert curve == {
        "1M": 4.0,
        "3M": 3.95,
        "6M": 3.9,
        "1Y": 3.8,
        "2Y": 3.6,
        "5Y": 3.7,
        "10Y": 4.0,
        "30Y": 4.4,
    }
    ten = next(p for p in batch.points if p.tenor == "10Y")
    assert ten.tenor_months == 120 and ten.curve is CurveType.NOMINAL
    assert ten.snapshot_id == "raw_treasury_x"
    months = [p.tenor_months for p in batch.points if p.observation_date == date(2026, 10, 16)]
    assert months == sorted(months)


def test_real_curve_and_explicit_gaps() -> None:
    batch = _batch("real.csv", CurveType.REAL)
    assert batch.curve_on(date(2026, 10, 15)) == {"5Y": 1.22, "7Y": 1.41, "10Y": 1.62, "30Y": 2.01}
    assert (date(2026, 10, 15), "20Y") in batch.missing
    assert (date(2026, 10, 15), "30Y") in _batch().missing


def test_same_day_curve_not_available_to_morning_decision() -> None:
    batch = _batch()
    morning = datetime(2026, 10, 16, 9, 30, tzinfo=NY)
    latest = batch.latest_curve_as_of(morning)
    assert latest is not None and latest[0] == date(2026, 10, 15)
    afternoon = datetime(2026, 10, 16, 16, 0, tzinfo=NY)
    assert batch.latest_curve_as_of(afternoon)[0] == date(2026, 10, 15)  # type: ignore[index]
    next_morning = datetime(2026, 10, 17, 9, 30, tzinfo=NY)
    assert batch.latest_curve_as_of(next_morning)[0] == date(2026, 10, 16)  # type: ignore[index]
    assert batch.latest_curve_as_of(datetime(2026, 10, 15, 12, 0, tzinfo=NY)) is None


def test_availability_is_conservative_inferred_eod() -> None:
    stamp = _batch().points[0].availability
    assert stamp.precision is AvailabilityPrecision.INFERRED_EOD
    assert stamp.available_at.astimezone(NY).time().hour == 23
    assert stamp.raw_available_date == date(2026, 10, 15)


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("1 Mo", ("1M", 1.0)),
        ("1.5 Month", ("1.5M", 1.5)),
        ("6 Wk", ("6W", 6 * 12 / 52)),
        ("30 YR", ("30Y", 360.0)),
        ("Bogus", None),
    ],
)
def test_tenor_parsing(column: str, expected: tuple[str, float] | None) -> None:
    assert parse_tenor(column) == expected


def test_unmapped_columns_reported_not_guessed() -> None:
    batch = _batch(text="Date,3 Mo,Extrapolation Factor\n10/16/2026,3.9,1.0\n")
    assert batch.unmapped_columns == ("Extrapolation Factor",)
    assert batch.curve_on(date(2026, 10, 16)) == {"3M": 3.9}


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("Day,3 Mo\n10/16/2026,3.9\n", "no Date column"),
        ("Date,Foo\n10/16/2026,1\n", "no maturity columns"),
        ("Date,3 Mo\n10/16/2026,3.9\n10/16/2026,3.8\n", "duplicate"),
        ("Date,3 Mo\n10/16/2026,abc\n", "not numeric"),
        ("Date,3 Mo\n16.10.2026,3.9\n", "unrecognised"),
        ("Date,3 Mo\n10/21/2026,3.9\n", "after the retrieval date"),
    ],
)
def test_schema_errors(text: str, match: str) -> None:
    with pytest.raises(ResponseSchemaError, match=match):
        _batch(text=text)


def test_fetch_builds_query_and_snapshot() -> None:
    seen: list[httpx.Request] = []
    body = (FIX / "real.csv").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=body)

    http = HttpClient(
        "us_treasury",
        transport=httpx.MockTransport(handler),
        sleep=lambda s: None,
        clock=lambda: RETRIEVED,
    )
    batch = fetch_treasury_curve(http, CurveType.REAL, 2026)
    assert seen[0].url.params["type"] == "daily_treasury_real_yield_curve"
    assert "/2026/all" in seen[0].url.path
    assert batch.snapshot_id.startswith("raw_us_treasury_")
