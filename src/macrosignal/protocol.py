"""Research protocol / hypothesis registry with frozen, immutable versions.

A :class:`ResearchProtocol` pre-registers what a study tests: hypothesis,
target, horizons, universe, metrics (with one primary metric), sample policy
and whether the study is exploratory or confirmatory
(``docs/EVALUATION_PROTOCOL.md``, ``docs/RESEARCH_QUESTIONS.md``).

:class:`ProtocolRegistry` stores each ``(protocol_id, version)`` as one canonical
JSON file carrying its content hash.  A registered version is frozen: writing
different content under the same version raises :class:`ProtocolMutationError`,
loading a file whose content no longer matches its hash raises
:class:`ProtocolIntegrityError`, and :meth:`ProtocolRegistry.require_for_run`
refuses runs that reference an unregistered protocol version.  Changing a
protocol therefore always means registering a new version.
"""

from __future__ import annotations

import json
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from macrosignal.domain.manifest import ResearchRun, canonical_json, stable_hash

ProtocolId = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$", max_length=64)]
Horizon = Annotated[str, Field(pattern=r"^[1-9][0-9]*[dwmq]$")]
MetricName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
AssetId = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9._-]*$")]
NonEmptyStr = Annotated[str, Field(min_length=1)]


class ProtocolStatus(StrEnum):
    EXPLORATORY = "exploratory"
    CONFIRMATORY = "confirmatory"


class SplitMethod(StrEnum):
    EXPANDING_WALK_FORWARD = "expanding_walk_forward"
    ROLLING_WALK_FORWARD = "rolling_walk_forward"


class SamplePolicy(BaseModel):
    """Chronological development / held-out test windows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    split_method: SplitMethod
    development_start: date
    development_end: date
    test_start: date | None = None
    test_end: date | None = None

    @model_validator(mode="after")
    def _check(self) -> SamplePolicy:
        problems: list[str] = []
        if self.development_end < self.development_start:
            problems.append("development_end is before development_start")
        if (self.test_start is None) != (self.test_end is None):
            problems.append("test_start and test_end must be given together")
        elif self.test_start is not None and self.test_end is not None:
            if self.test_end < self.test_start:
                problems.append("test_end is before test_start")
            if self.test_start <= self.development_end:
                problems.append("test window must start after the development window ends")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class ResearchProtocol(BaseModel):
    """A pre-registered hypothesis and evaluation plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_id: ProtocolId
    version: Annotated[int, Field(ge=1)]
    status: ProtocolStatus
    hypothesis: NonEmptyStr
    null_result_statement: NonEmptyStr
    target: NonEmptyStr
    horizons: tuple[Horizon, ...] = Field(min_length=1)
    universe: tuple[AssetId, ...] = Field(min_length=1)
    metrics: tuple[MetricName, ...] = Field(min_length=1)
    primary_metric: MetricName
    sample_policy: SamplePolicy
    registered_at: AwareDatetime
    notes: str = ""

    @model_validator(mode="after")
    def _check(self) -> ResearchProtocol:
        problems: list[str] = []
        for name in ("horizons", "universe", "metrics"):
            values = getattr(self, name)
            if len(set(values)) != len(values):
                problems.append(f"{name} contains duplicates")
        if self.primary_metric not in self.metrics:
            problems.append("primary_metric must be one of metrics")
        if self.status is ProtocolStatus.CONFIRMATORY and self.sample_policy.test_start is None:
            problems.append("a confirmatory protocol requires an untouched held-out test window")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def content_hash(self) -> str:
        return stable_hash(self)

    @property
    def version_label(self) -> str:
        return str(self.version)


class ProtocolMutationError(RuntimeError):
    """Attempt to change an already registered (frozen) protocol version."""


class ProtocolIntegrityError(RuntimeError):
    """A stored protocol no longer matches its recorded hash."""


class ProtocolNotFoundError(KeyError):
    """No registered protocol for the requested id/version."""


class ProtocolRegistry:
    """File-backed registry: ``<root>/<protocol_id>/v<version>.json``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def path_for(self, protocol_id: str, version: int) -> Path:
        return self.root / protocol_id / f"v{version}.json"

    def register(self, protocol: ResearchProtocol) -> ResearchProtocol:
        """Freeze ``protocol``; identical re-registration is a no-op."""
        path = self.path_for(protocol.protocol_id, protocol.version)
        if path.exists():
            existing = self._load(path)
            if existing.content_hash == protocol.content_hash:
                return existing
            raise ProtocolMutationError(
                f"protocol {protocol.protocol_id} v{protocol.version} is frozen; register a new "
                "version instead of editing it"
            )
        versions = self.versions(protocol.protocol_id)
        if versions and protocol.version != versions[-1] + 1:
            raise ValueError(
                f"next version of {protocol.protocol_id} must be {versions[-1] + 1}, "
                f"got {protocol.version}"
            )
        if not versions and protocol.version != 1:
            raise ValueError("the first registered version must be 1")
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"content_hash": protocol.content_hash, "protocol": protocol}
        with path.open("x", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(record) + "\n")
        return protocol

    def _load(self, path: Path) -> ResearchProtocol:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        protocol = ResearchProtocol.model_validate(data["protocol"])
        if protocol.content_hash != data.get("content_hash"):
            raise ProtocolIntegrityError(f"{path} content does not match its recorded hash")
        return protocol

    def get(self, protocol_id: str, version: int) -> ResearchProtocol:
        path = self.path_for(protocol_id, version)
        if not path.exists():
            raise ProtocolNotFoundError(f"{protocol_id} v{version}")
        return self._load(path)

    def versions(self, protocol_id: str) -> list[int]:
        folder = self.root / protocol_id
        if not folder.is_dir():
            return []
        out = []
        for p in folder.glob("v*.json"):
            stem = p.stem[1:]
            if stem.isdigit():
                out.append(int(stem))
        return sorted(out)

    def latest(self, protocol_id: str) -> ResearchProtocol:
        versions = self.versions(protocol_id)
        if not versions:
            raise ProtocolNotFoundError(protocol_id)
        return self.get(protocol_id, versions[-1])

    def require_for_run(self, run: ResearchRun) -> ResearchProtocol:
        """Return the frozen protocol a run references, or raise."""
        if not run.protocol_version.isdigit():
            raise ProtocolNotFoundError(
                f"run protocol_version {run.protocol_version!r} is not a registered version number"
            )
        return self.get(run.protocol_id, int(run.protocol_version))
