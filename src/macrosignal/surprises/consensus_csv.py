"""Timestamped consensus CSV adapter (user-supplied, never redistributed).

Imports the documented consensus schema (``examples/consensus_template.csv``)::

    release_id,reference_period,expected_value,forecast_created_at,available_at,
    expectation_source,expectation_type[,release_stage][,units]

``release_id`` is the release family (e.g. ``CPI``) and ``reference_period`` is
``YYYY-MM`` or ``YYYY-Qn``; together (plus the optional ``release_stage``) they
must match exactly one released calendar event.  Timestamps must carry a UTC
offset.  Only ``consensus`` rows are accepted.

Every row ends up either accepted (a :class:`ConsensusExpectation` keyed to the
matched event's ``release_id``) or listed in the :class:`ConsensusImportReport`
as unmatched, ambiguous, post-release (available at/after the actual release)
or invalid - nothing is guessed or dropped silently.

The file is read from a user-chosen path (keep licensed data outside the
repository, e.g. under the git-ignored ``data/``); the snapshot id is a hash of
its bytes so results stay traceable without committing the data.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterable, Mapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from macrosignal.domain import (
    ConsensusExpectation,
    ExpectationChronologyError,
    ExpectationType,
    ReleaseEvent,
    SurpriseMode,
    check_pre_release,
)
from macrosignal.fixtures import parse_reference_period
from macrosignal.surprises.expectations import StaticExpectationProvider

REQUIRED_COLUMNS = (
    "release_id",
    "reference_period",
    "expected_value",
    "forecast_created_at",
    "available_at",
    "expectation_source",
    "expectation_type",
)


class RowProblem(StrEnum):
    INVALID = "invalid"
    UNMATCHED = "unmatched"
    AMBIGUOUS = "ambiguous"
    POST_RELEASE = "post_release"


class RowIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    line: int
    problem: RowProblem
    detail: str


class ConsensusImportReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_snapshot_id: str
    rows_total: int
    accepted: int
    issues: tuple[RowIssue, ...]

    def count(self, problem: RowProblem) -> int:
        return sum(1 for i in self.issues if i.problem is problem)


class ConsensusImport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expectations: tuple[ConsensusExpectation, ...]
    report: ConsensusImportReport

    def provider(self, name: str = "consensus_csv") -> StaticExpectationProvider:
        return StaticExpectationProvider(name, ExpectationType.CONSENSUS, self.expectations)


def _aware(value: str, column: str) -> datetime:
    ts = datetime.fromisoformat(value.strip())
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError(f"{column} {value!r} has no UTC offset")
    return ts


def import_consensus_csv(
    text: str,
    events: Iterable[ReleaseEvent],
    *,
    default_units: Mapping[str, str] | None = None,
    source_snapshot_id: str | None = None,
) -> ConsensusImport:
    snapshot = source_snapshot_id or (
        "consensus_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
    )
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"consensus CSV is missing columns {missing}")
    released = [e for e in events if e.actual_release_at is not None]
    accepted: list[ConsensusExpectation] = []
    issues: list[RowIssue] = []
    total = 0
    for line, row in enumerate(reader, start=2):
        total += 1

        def issue(problem: RowProblem, detail: str, _line: int = line) -> None:
            issues.append(RowIssue(line=_line, problem=problem, detail=detail))

        try:
            if row["expectation_type"].strip() != "consensus":
                raise ValueError(f"expectation_type {row['expectation_type']!r} is not consensus")
            family = row["release_id"].strip()
            ref_start, ref_end, _ = parse_reference_period(row["reference_period"].strip())
            created = _aware(row["forecast_created_at"], "forecast_created_at")
            available = _aware(row["available_at"], "available_at")
            value = float(row["expected_value"])
            units = (row.get("units") or "").strip() or (default_units or {}).get(family)
            if not units:
                raise ValueError(f"no units for {family}; add a units column or default_units")
            stage = (row.get("release_stage") or "").strip() or None
        except (ValueError, KeyError) as exc:
            issue(RowProblem.INVALID, str(exc))
            continue

        matches = [
            e
            for e in released
            if e.release_family == family
            and e.reference_start == ref_start
            and e.reference_end == ref_end
            and (stage is None or (e.release_stage is not None and e.release_stage.value == stage))
        ]
        if not matches:
            issue(RowProblem.UNMATCHED, f"no released {family} event for {row['reference_period']}")
            continue
        if len(matches) > 1:
            ids = sorted(e.release_id for e in matches)
            issue(RowProblem.AMBIGUOUS, f"matches several events {ids}; add release_stage")
            continue
        event = matches[0]
        try:
            exp = ConsensusExpectation(
                release_id=event.release_id,
                reference_start=ref_start,
                reference_end=ref_end,
                expected_value=value,
                units=units,
                expectation_source=row["expectation_source"].strip(),
                forecast_created_at=created,
                availability={
                    "available_at": available,
                    "precision": "provider_timestamp",  # type: ignore[arg-type]
                    "availability_source": "provider_timestamp",
                },
                source_snapshot_id=snapshot,
            )
        except ValidationError as exc:
            issue(RowProblem.INVALID, exc.errors()[0]["msg"])
            continue
        try:
            check_pre_release(exp, event, SurpriseMode.MARKET_SURPRISE)
        except ExpectationChronologyError as exc:
            issue(RowProblem.POST_RELEASE, str(exc))
            continue
        accepted.append(exp)

    report = ConsensusImportReport(
        source_snapshot_id=snapshot, rows_total=total, accepted=len(accepted), issues=tuple(issues)
    )
    return ConsensusImport(expectations=tuple(accepted), report=report)


def import_consensus_file(
    path: Path | str, events: Iterable[ReleaseEvent], **kwargs: object
) -> ConsensusImport:
    return import_consensus_csv(Path(path).read_text(encoding="utf-8"), events, **kwargs)  # type: ignore[arg-type]
