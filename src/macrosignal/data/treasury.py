"""U.S. Treasury daily nominal (par) and real yield-curve adapter.

Treasury publishes the daily par yield curve and the daily real (TIPS) yield
curve as CSV, one row per business day and one column per maturity
(``1 Mo`` ... ``30 Yr``; real curve ``5 YR`` ... ``30 YR``), dates as
``MM/DD/YYYY``.  This adapter normalizes each cell into a
:class:`YieldCurvePoint` with a canonical tenor and month count.

Availability: Treasury states the par-curve input quotations are obtained at
approximately 3:30 PM ET, and the curve is published after that.  The exact
publication time is not part of the data, so each point is stamped
conservatively at the end of its observation date in New York
(precision ``inferred_eod``, source ``conservative_inference``).  A decision
on the morning of the same day therefore can never consume that day's curve;
the next morning it can.

Blank / ``N/A`` cells are recorded as explicit gaps (never filled), unknown
columns are reported in ``unmapped_columns`` instead of being guessed, and
duplicate dates are rejected.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, time
from enum import StrEnum
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from macrosignal.data.http import HttpClient, ResponseSchemaError
from macrosignal.domain import AvailabilityPrecision, AvailabilitySource, AvailabilityStamp

TREASURY_TIMEZONE = ZoneInfo("America/New_York")
SOURCE = "us_treasury"
ADAPTER_VERSION = "treasury-curve-1"
END_OF_DAY = time(23, 59, 59)

TREASURY_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
)


class CurveType(StrEnum):
    NOMINAL = "nominal"
    REAL = "real"


CURVE_QUERY_TYPE = {
    CurveType.NOMINAL: "daily_treasury_yield_curve",
    CurveType.REAL: "daily_treasury_real_yield_curve",
}

_COLUMN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(MO|MONTH|MONTHS|WK|WEEK|WEEKS|YR|YEAR|YEARS)\s*$", re.I
)


def parse_tenor(column: str) -> tuple[str, float] | None:
    """``"3 Mo"`` -> ``("3M", 3.0)``; ``"10 YR"`` -> ``("10Y", 120.0)``; else None."""
    m = _COLUMN.match(column)
    if not m:
        return None
    n = float(m.group(1))
    unit = m.group(2).upper()
    label = m.group(1)
    if unit.startswith("MO"):
        return f"{label}M", n
    if unit.startswith("W"):
        return f"{label}W", n * 12 / 52
    return f"{label}Y", n * 12


class YieldCurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = SOURCE
    curve: CurveType
    observation_date: date
    tenor: Annotated[str, Field(pattern=r"^\d+(\.\d+)?[WMY]$")]
    tenor_months: Annotated[float, Field(gt=0)]
    yield_pct: FiniteFloat
    availability: AvailabilityStamp
    snapshot_id: str
    retrieved_at: datetime
    adapter_version: str = ADAPTER_VERSION


class YieldCurveBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    curve: CurveType
    points: tuple[YieldCurvePoint, ...]
    missing: tuple[tuple[date, str], ...]
    unmapped_columns: tuple[str, ...]
    snapshot_id: str

    def curve_on(self, day: date) -> dict[str, float]:
        return {p.tenor: p.yield_pct for p in self.points if p.observation_date == day}

    def available_at(self, decision_time: datetime) -> list[YieldCurvePoint]:
        """Points knowable at ``decision_time`` (PIT golden rule)."""
        return [p for p in self.points if p.availability.is_available_at(decision_time)]

    def latest_curve_as_of(self, decision_time: datetime) -> tuple[date, dict[str, float]] | None:
        usable = self.available_at(decision_time)
        if not usable:
            return None
        day = max(p.observation_date for p in usable)
        return day, {p.tenor: p.yield_pct for p in usable if p.observation_date == day}


def curve_availability(observation_date: date) -> AvailabilityStamp:
    available_at = datetime.combine(observation_date, END_OF_DAY, tzinfo=TREASURY_TIMEZONE)
    midnight = datetime.combine(observation_date, time(0, 0), tzinfo=TREASURY_TIMEZONE)
    return AvailabilityStamp(
        available_at=available_at,
        precision=AvailabilityPrecision.INFERRED_EOD,
        availability_source=AvailabilitySource.CONSERVATIVE_INFERENCE,
        raw_available_date=observation_date,
        conservative_adjustment=available_at - midnight,
        resolver_version=ADAPTER_VERSION,
    )


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ResponseSchemaError(f"unrecognised Treasury date {value!r}")


def parse_treasury_csv(
    text: str, curve: CurveType, *, snapshot_id: str, retrieved_at: datetime
) -> YieldCurveBatch:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    fields = [f for f in (reader.fieldnames or [])]
    date_col = next((f for f in fields if f.strip().lower() == "date"), None)
    if date_col is None:
        raise ResponseSchemaError("Treasury CSV has no Date column")
    tenors: dict[str, tuple[str, float]] = {}
    unmapped: list[str] = []
    for f in fields:
        if f == date_col:
            continue
        parsed = parse_tenor(f)
        if parsed is None:
            unmapped.append(f)
        else:
            tenors[f] = parsed
    if not tenors:
        raise ResponseSchemaError("Treasury CSV has no maturity columns")
    points: list[YieldCurvePoint] = []
    missing: list[tuple[date, str]] = []
    seen: set[date] = set()
    for row in reader:
        day = _parse_date(row[date_col])
        if day in seen:
            raise ResponseSchemaError(f"duplicate Treasury curve date {day}")
        seen.add(day)
        if retrieved_at.astimezone(TREASURY_TIMEZONE).date() < day:
            raise ResponseSchemaError(f"curve date {day} is after the retrieval date")
        stamp = curve_availability(day)
        for column, (tenor, months) in tenors.items():
            raw = (row.get(column) or "").strip()
            if raw in ("", "N/A", "NA"):
                missing.append((day, tenor))
                continue
            try:
                value = float(raw)
            except ValueError as exc:
                raise ResponseSchemaError(f"{day} {column}: {raw!r} is not numeric") from exc
            points.append(
                YieldCurvePoint(
                    curve=curve,
                    observation_date=day,
                    tenor=tenor,
                    tenor_months=months,
                    yield_pct=value,
                    availability=stamp,
                    snapshot_id=snapshot_id,
                    retrieved_at=retrieved_at,
                )
            )
    points.sort(key=lambda p: (p.observation_date, p.tenor_months))
    return YieldCurveBatch(
        curve=curve,
        points=tuple(points),
        missing=tuple(sorted(missing)),
        unmapped_columns=tuple(unmapped),
        snapshot_id=snapshot_id,
    )


def fetch_treasury_curve(
    http: HttpClient, curve: CurveType, year: int, *, url_template: str = TREASURY_CSV_URL
) -> YieldCurveBatch:
    url = url_template.format(year=year)
    params = {
        "type": CURVE_QUERY_TYPE[curve],
        "field_tdr_date_value": str(year),
        "page": "",
        "_format": "csv",
    }
    response = http.get(url, params)
    return parse_treasury_csv(
        response.content.decode("utf-8"),
        curve,
        snapshot_id=response.snapshot.snapshot_id,
        retrieved_at=response.snapshot.retrieved_at,
    )
