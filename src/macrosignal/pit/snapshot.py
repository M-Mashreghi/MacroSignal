"""Immutable point-in-time snapshot builder with a precision quality report.

A :class:`PitSnapshot` freezes the result of ``PitStore.as_of(t)`` together
with everything needed to reproduce and audit it: the as-of time, the rows,
the raw source snapshot ids they came from, the availability resolver version,
the config hash and the code commit.  Its ``pit_snapshot_id`` is a stable hash
of those canonical inputs (``created_at`` excluded), so rebuilding the same
snapshot yields the same id, and the validator rejects tampering or any row
not available at ``as_of``.

Every snapshot carries a :class:`PrecisionQualityReport` counting rows by
availability precision and listing those with ``inferred_eod`` / ``unknown``
timing, and is persisted as an immutable ``pit_snapshot`` artifact
(``snapshot.json`` + ``quality_report.json``).
"""

from __future__ import annotations

import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from macrosignal.artifacts import ArtifactKind, ArtifactRecord, ArtifactRegistry
from macrosignal.domain import AvailabilityPrecision, MacroObservation
from macrosignal.domain.manifest import canonical_json, stable_hash
from macrosignal.pit.as_of import AsOfResult, PitStore

CodeCommit = Annotated[str, Field(pattern=r"^[0-9a-f]{7,40}(-dirty)?$")]
Sha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]

FLAGGED_PRECISIONS = (AvailabilityPrecision.INFERRED_EOD, AvailabilityPrecision.UNKNOWN)


class FlaggedRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    series_id: str
    reference_start: str
    precision: AvailabilityPrecision


class PrecisionQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_rows: int
    counts_by_precision: dict[str, int]
    flagged: tuple[FlaggedRow, ...]
    excluded_for_precision: tuple[str, ...] = ()

    @property
    def flagged_share(self) -> float:
        return len(self.flagged) / self.total_rows if self.total_rows else 0.0


def quality_report(
    rows: tuple[MacroObservation, ...], excluded: tuple[str, ...] = ()
) -> PrecisionQualityReport:
    counts = Counter(r.availability.precision.value for r in rows)
    flagged = tuple(
        FlaggedRow(
            source=r.source,
            series_id=r.series_id,
            reference_start=r.reference_start.isoformat(),
            precision=r.availability.precision,
        )
        for r in rows
        if r.availability.precision in FLAGGED_PRECISIONS
    )
    return PrecisionQualityReport(
        total_rows=len(rows),
        counts_by_precision={p.value: counts.get(p.value, 0) for p in AvailabilityPrecision},
        flagged=flagged,
        excluded_for_precision=excluded,
    )


def _row_key(o: MacroObservation) -> tuple[str, str, str]:
    return (o.source, o.series_id, o.reference_start.isoformat())


class PitSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pit_snapshot_id: str
    as_of: AwareDatetime
    rows: tuple[MacroObservation, ...]
    source_snapshot_ids: tuple[str, ...]
    resolver_version: Annotated[str, Field(min_length=1)]
    config_hash: Sha256
    code_commit: CodeCommit
    created_at: AwareDatetime
    quality: PrecisionQualityReport

    @staticmethod
    def identity(
        as_of: datetime,
        rows: tuple[MacroObservation, ...],
        source_snapshot_ids: tuple[str, ...],
        resolver_version: str,
        config_hash: str,
        code_commit: str,
    ) -> dict[str, Any]:
        return {
            "as_of": as_of,
            "rows": [r.model_dump(mode="python") for r in rows],
            "source_snapshot_ids": list(source_snapshot_ids),
            "resolver_version": resolver_version,
            "config_hash": config_hash,
            "code_commit": code_commit,
        }

    @property
    def content_hash(self) -> str:
        return stable_hash(
            self.identity(
                self.as_of,
                self.rows,
                self.source_snapshot_ids,
                self.resolver_version,
                self.config_hash,
                self.code_commit,
            )
        )

    @model_validator(mode="after")
    def _check(self) -> PitSnapshot:
        problems: list[str] = []
        if list(self.rows) != sorted(self.rows, key=_row_key):
            problems.append("rows must be sorted by (source, series_id, reference_start)")
        late = [r for r in self.rows if r.availability.available_at > self.as_of]
        if late:
            problems.append(f"{len(late)} row(s) not available at as_of")
        expected_sources = tuple(sorted({r.source_snapshot_id for r in self.rows}))
        if self.source_snapshot_ids != expected_sources:
            problems.append("source_snapshot_ids must equal the rows' sorted unique snapshot ids")
        if self.created_at < self.as_of:
            problems.append("created_at precedes as_of")
        expected_id = f"pit_{self.content_hash.removeprefix('sha256:')[:24]}"
        if not problems and self.pit_snapshot_id != expected_id:
            problems.append(f"pit_snapshot_id does not match content ({expected_id})")
        if problems:
            raise ValueError("; ".join(problems))
        return self


def build_pit_snapshot(
    store: PitStore | AsOfResult,
    as_of: datetime,
    *,
    resolver_version: str,
    config_hash: str,
    code_commit: str,
    created_at: datetime,
    min_precision: AvailabilityPrecision | None = None,
) -> PitSnapshot:
    result = (
        store if isinstance(store, AsOfResult) else store.as_of(as_of, min_precision=min_precision)
    )
    if result.as_of != as_of:
        raise ValueError("AsOfResult was computed for a different as_of time")
    rows = tuple(sorted(result.observations.values(), key=_row_key))
    sources = tuple(sorted({r.source_snapshot_id for r in rows}))
    content = stable_hash(
        PitSnapshot.identity(as_of, rows, sources, resolver_version, config_hash, code_commit)
    )
    excluded = tuple(
        f"{s}:{sid}:{ref.isoformat()}" for s, sid, ref in result.excluded_for_precision
    )
    return PitSnapshot(
        pit_snapshot_id=f"pit_{content.removeprefix('sha256:')[:24]}",
        as_of=as_of,
        rows=rows,
        source_snapshot_ids=sources,
        resolver_version=resolver_version,
        config_hash=config_hash,
        code_commit=code_commit,
        created_at=created_at,
        quality=quality_report(rows, excluded),
    )


def persist_pit_snapshot(registry: ArtifactRegistry, snapshot: PitSnapshot) -> ArtifactRecord:
    body = snapshot.model_dump(mode="python", exclude={"created_at", "quality"})
    return registry.register(
        ArtifactKind.PIT_SNAPSHOT,
        snapshot.pit_snapshot_id,
        {
            "snapshot.json": canonical_json(body).encode("utf-8"),
            "quality_report.json": canonical_json(snapshot.quality).encode("utf-8"),
        },
        created_at=snapshot.created_at,
        snapshot_id=snapshot.pit_snapshot_id,
        metadata={
            "as_of": snapshot.as_of.isoformat(),
            "rows": len(snapshot.rows),
            "flagged_rows": len(snapshot.quality.flagged),
        },
    )


def current_code_commit(root: Path) -> str:
    """``git rev-parse HEAD`` plus ``-dirty`` when the working tree has changes."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    return f"{head}-dirty" if dirty else head
