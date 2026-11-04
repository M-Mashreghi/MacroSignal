"""Artifact registry and deterministic local storage layout.

Every research artifact (raw source snapshot, PIT snapshot, feature set, model
fit, backtest, report) lives at a deterministic path derived from its kind and
id, and is recorded in an append-only JSON-lines registry with a content hash
and its run / snapshot / model-fit linkage.

Artifacts are immutable: registering the same id again with identical content
is an idempotent no-op, while different content raises
:class:`ImmutableArtifactError` instead of overwriting.

Layout (relative to the configured data / reports directories)::

    data/raw/<source>/<artifact_id>/        raw_snapshot
    data/processed/normalized/<artifact_id>/normalized
    data/snapshots/pit/<artifact_id>/       pit_snapshot
    data/processed/features/<artifact_id>/  features
    data/processed/model_fits/<artifact_id>/model_fit
    reports/runs/<artifact_id>/backtest/    backtest
    reports/runs/<artifact_id>/report/      report
    data/registry/artifacts.jsonl           registry
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import time
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from macrosignal.domain.manifest import canonical_json, stable_hash

SafeId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", max_length=128)]
Sha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]

REGISTRY_RELATIVE_PATH = PurePosixPath("registry/artifacts.jsonl")
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


class ArtifactKind(StrEnum):
    RAW_SNAPSHOT = "raw_snapshot"
    NORMALIZED = "normalized"
    PIT_SNAPSHOT = "pit_snapshot"
    FEATURES = "features"
    MODEL_FIT = "model_fit"
    BACKTEST = "backtest"
    REPORT = "report"


class ImmutableArtifactError(RuntimeError):
    """An attempt to overwrite an existing artifact with different content."""


class ArtifactNotFoundError(KeyError):
    """No artifact with the requested id is registered."""


class ArtifactRecord(BaseModel):
    """One registry entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: SafeId
    kind: ArtifactKind
    root: Annotated[str, Field(pattern=r"^(data|reports)$")]
    relative_path: str
    content_hash: Sha256
    files: tuple[str, ...]
    source: SafeId | None = None
    run_id: SafeId | None = None
    snapshot_id: SafeId | None = None
    model_fit_id: SafeId | None = None
    created_at: AwareDatetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> ArtifactRecord:
        if self.kind is ArtifactKind.RAW_SNAPSHOT and self.source is None:
            raise ValueError("raw_snapshot artifacts require a source")
        if self.kind is ArtifactKind.MODEL_FIT and self.model_fit_id not in (
            None,
            self.artifact_id,
        ):
            raise ValueError("model_fit artifact_id must equal model_fit_id")
        return self


def _validate_relpath(name: str) -> str:
    p = PurePosixPath(name)
    if not name or p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
        raise ValueError(f"unsafe artifact file path {name!r}")
    return p.as_posix()


def content_hash(files: Mapping[str, bytes]) -> str:
    """Stable hash over sorted (relative path, sha256(bytes)) pairs."""
    entries = sorted(
        (_validate_relpath(name), hashlib.sha256(data).hexdigest()) for name, data in files.items()
    )
    return stable_hash([list(e) for e in entries])


class ArtifactRegistry:
    """Deterministic artifact storage plus an append-only registry file."""

    def __init__(self, data_dir: Path | str, reports_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)
        self.reports_dir = Path(reports_dir)

    # --- layout -------------------------------------------------------------
    @property
    def registry_path(self) -> Path:
        return self.data_dir / REGISTRY_RELATIVE_PATH

    @staticmethod
    def layout(kind: ArtifactKind, artifact_id: str, source: str | None = None) -> tuple[str, str]:
        """Return ``(root, relative_path)`` for an artifact; pure and deterministic."""
        _check_id(artifact_id)
        if kind is ArtifactKind.RAW_SNAPSHOT:
            if source is None:
                raise ValueError("raw_snapshot artifacts require a source")
            _check_id(source)
            return "data", f"raw/{source}/{artifact_id}"
        if kind is ArtifactKind.NORMALIZED:
            return "data", f"processed/normalized/{artifact_id}"
        if kind is ArtifactKind.PIT_SNAPSHOT:
            return "data", f"snapshots/pit/{artifact_id}"
        if kind is ArtifactKind.FEATURES:
            return "data", f"processed/features/{artifact_id}"
        if kind is ArtifactKind.MODEL_FIT:
            return "data", f"processed/model_fits/{artifact_id}"
        if kind is ArtifactKind.BACKTEST:
            return "reports", f"runs/{artifact_id}/backtest"
        return "reports", f"runs/{artifact_id}/report"

    def _root_dir(self, root: str) -> Path:
        return self.data_dir if root == "data" else self.reports_dir

    def path_for(self, kind: ArtifactKind, artifact_id: str, source: str | None = None) -> Path:
        root, rel = self.layout(kind, artifact_id, source)
        return self._root_dir(root) / rel

    def path_of(self, record: ArtifactRecord) -> Path:
        return self._root_dir(record.root) / record.relative_path

    # --- registry I/O -------------------------------------------------------------
    def records(self) -> list[ArtifactRecord]:
        if not self.registry_path.exists():
            return []
        out: list[ArtifactRecord] = []
        with self.registry_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    out.append(ArtifactRecord.model_validate_json(line))
        return out

    def _append(self, record: ArtifactRecord) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.registry_path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(record) + "\n")

    # --- operations ---------------------------------------------------------------
    def register(
        self,
        kind: ArtifactKind,
        artifact_id: str,
        files: Mapping[str, bytes],
        *,
        created_at: datetime,
        source: str | None = None,
        run_id: str | None = None,
        snapshot_id: str | None = None,
        model_fit_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRecord:
        """Write and register an artifact; identical re-registration is a no-op."""
        if not files:
            raise ValueError("an artifact needs at least one file")
        if kind is ArtifactKind.MODEL_FIT and model_fit_id is None:
            model_fit_id = artifact_id
        root, rel = self.layout(kind, artifact_id, source)
        digest = content_hash(files)
        record = ArtifactRecord(
            artifact_id=artifact_id,
            kind=kind,
            root=root,
            relative_path=rel,
            content_hash=digest,
            files=tuple(sorted(_validate_relpath(n) for n in files)),
            source=source,
            run_id=run_id,
            snapshot_id=snapshot_id,
            model_fit_id=model_fit_id,
            created_at=created_at,
            metadata=dict(metadata or {}),
        )

        existing = self._find(artifact_id)
        target = self._root_dir(root) / rel
        if existing is not None:
            if existing.kind is kind and existing.content_hash == digest:
                return existing
            raise ImmutableArtifactError(
                f"artifact {artifact_id!r} already registered with different "
                f"{'kind' if existing.kind is not kind else 'content'}; refusing to overwrite"
            )
        if target.exists():
            raise ImmutableArtifactError(
                f"unregistered files already exist at {target}; refusing to overwrite"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=target.parent))
        try:
            for name, data in files.items():
                dest = staging / _validate_relpath(name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            _replace_with_retry(staging, target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        self._append(record)
        return record

    def _find(self, artifact_id: str) -> ArtifactRecord | None:
        for record in self.records():
            if record.artifact_id == artifact_id:
                return record
        return None

    def get(self, artifact_id: str) -> ArtifactRecord:
        record = self._find(artifact_id)
        if record is None:
            raise ArtifactNotFoundError(artifact_id)
        return record

    def by_run(self, run_id: str) -> list[ArtifactRecord]:
        return [r for r in self.records() if r.run_id == run_id]

    def by_snapshot(self, snapshot_id: str) -> list[ArtifactRecord]:
        return [r for r in self.records() if r.snapshot_id == snapshot_id]

    def by_model_fit(self, model_fit_id: str) -> list[ArtifactRecord]:
        return [r for r in self.records() if r.model_fit_id == model_fit_id]

    def read_files(self, artifact_id: str) -> dict[str, bytes]:
        record = self.get(artifact_id)
        base = self.path_of(record)
        return {name: (base / name).read_bytes() for name in record.files}

    def verify(self, artifact_id: str) -> bool:
        """Recompute the stored files' hash and compare with the registry."""
        record = self.get(artifact_id)
        try:
            files = self.read_files(artifact_id)
        except FileNotFoundError:
            return False
        return content_hash(files) == record.content_hash


def _replace_with_retry(src: Path, dst: Path, attempts: int = 5) -> None:
    """``os.replace`` that tolerates transient Windows sharing locks (AV / indexer)."""
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1 or dst.exists():
                raise
            time.sleep(0.05 * (attempt + 1))


def _check_id(value: str) -> None:
    if not _SAFE_ID.fullmatch(value) or len(value) > 128:
        raise ValueError(f"unsafe artifact id {value!r}")


def dump_json_bytes(payload: Any) -> bytes:
    """Canonical JSON bytes, convenient for manifest-like artifact files."""
    return canonical_json(payload).encode("utf-8")


__all__ = [
    "ArtifactKind",
    "ArtifactNotFoundError",
    "ArtifactRecord",
    "ArtifactRegistry",
    "ImmutableArtifactError",
    "content_hash",
    "dump_json_bytes",
]
