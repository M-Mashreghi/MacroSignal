"""Immutable ResearchSnapshot / ResearchRun manifests with stable hashing.

A manifest must let someone audit a run later without consulting mutable
"latest" configuration files.  Therefore:

* every config a run used is embedded as a :class:`ConfigRecord` (content plus
  its stable hash), not just referenced by path;
* serialization is canonical (:func:`canonical_json`: sorted keys, compact
  separators, UTC ISO timestamps, no NaN/inf) so hashes are reproducible across
  machines and Python versions;
* snapshot and run ids are derived from the identity content (everything except
  ``created_at``), so rebuilding the same inputs yields the same id, and the
  validators reject ids that do not match their content.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import UTC, date, datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

NonEmptyStr = Annotated[str, Field(min_length=1)]
CodeCommit = Annotated[str, Field(pattern=r"^[0-9a-f]{7,40}(-dirty)?$")]
Sha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]

#: Config slots every research run must embed.
RUN_CONFIG_SLOTS = ("feature", "regime", "signal", "portfolio", "execution")


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python"))
    if isinstance(value, Enum):
        return _normalize(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"naive datetime {value!r} cannot be canonically serialized")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"mapping key {k!r} must be a string")
            out[k] = _normalize(v)
        return out
    if isinstance(value, list | tuple):
        return [_normalize(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats cannot be canonically serialized")
        return value
    raise TypeError(f"unsupported type for canonical serialization: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Deterministic JSON text for hashing and storage."""
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def stable_hash(value: Any) -> str:
    """``sha256:<hex>`` of :func:`canonical_json` of ``value``."""
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_canonical_json(self) -> str:
        return canonical_json(self)

    @property
    def manifest_hash(self) -> str:
        return stable_hash(self)


class ConfigRecord(_Manifest):
    """A frozen copy of one configuration's content and its stable hash."""

    name: NonEmptyStr
    source_path: NonEmptyStr
    content: dict[str, Any]
    sha256: Sha256

    @model_validator(mode="after")
    def _check_hash(self) -> ConfigRecord:
        actual = stable_hash(self.content)
        if actual != self.sha256:
            raise ValueError(
                f"config {self.name!r} content hash {actual} != recorded {self.sha256}"
            )
        return self

    @classmethod
    def from_content(cls, name: str, source_path: str, content: Mapping[str, Any]) -> ConfigRecord:
        data = dict(content)
        return cls(name=name, source_path=source_path, content=data, sha256=stable_hash(data))


def _derived_id(prefix: str, identity: Mapping[str, Any]) -> str:
    return f"{prefix}_{stable_hash(identity).removeprefix('sha256:')[:20]}"


class ResearchSnapshot(_Manifest):
    """Identity of the frozen inputs a research run reads."""

    snapshot_id: NonEmptyStr
    as_of: AwareDatetime
    input_snapshot_ids: tuple[NonEmptyStr, ...]
    config_hash: Sha256
    code_commit: CodeCommit
    created_at: AwareDatetime

    @staticmethod
    def identity_of(
        as_of: datetime, input_snapshot_ids: tuple[str, ...], config_hash: str, code_commit: str
    ) -> dict[str, Any]:
        return {
            "as_of": as_of,
            "input_snapshot_ids": sorted(input_snapshot_ids),
            "config_hash": config_hash,
            "code_commit": code_commit,
        }

    @classmethod
    def create(
        cls,
        *,
        as_of: datetime,
        input_snapshot_ids: tuple[str, ...] | list[str],
        config_hash: str,
        code_commit: str,
        created_at: datetime,
    ) -> ResearchSnapshot:
        ids = tuple(sorted(input_snapshot_ids))
        identity = cls.identity_of(as_of, ids, config_hash, code_commit)
        return cls(
            snapshot_id=_derived_id("snap", identity),
            as_of=as_of,
            input_snapshot_ids=ids,
            config_hash=config_hash,
            code_commit=code_commit,
            created_at=created_at,
        )

    @model_validator(mode="after")
    def _check(self) -> ResearchSnapshot:
        problems: list[str] = []
        ids = self.input_snapshot_ids
        if not ids:
            problems.append("input_snapshot_ids must not be empty")
        if list(ids) != sorted(set(ids)):
            problems.append("input_snapshot_ids must be sorted and unique")
        if self.created_at < self.as_of:
            problems.append("created_at precedes as_of; a snapshot cannot contain the future")
        expected = _derived_id(
            "snap",
            self.identity_of(self.as_of, ids, self.config_hash, self.code_commit),
        )
        if not problems and self.snapshot_id != expected:
            problems.append(f"snapshot_id {self.snapshot_id!r} does not match content ({expected})")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class ResearchRun(_Manifest):
    """One research run: snapshot, frozen protocol, embedded configs, seed and code."""

    run_id: NonEmptyStr
    snapshot_id: NonEmptyStr
    protocol_id: NonEmptyStr
    protocol_version: NonEmptyStr
    configs: dict[str, ConfigRecord]
    feature_config_hash: Sha256
    regime_config_hash: Sha256
    signal_config_hash: Sha256
    portfolio_config_hash: Sha256
    execution_config_hash: Sha256
    search_registry_id: NonEmptyStr
    seed: Annotated[int, Field(ge=0)]
    code_commit: CodeCommit
    created_at: AwareDatetime

    def _identity(self) -> dict[str, Any]:
        data = self.model_dump(mode="python", exclude={"run_id", "created_at"})
        return dict(data)

    @classmethod
    def create(
        cls,
        *,
        snapshot: ResearchSnapshot,
        protocol_id: str,
        protocol_version: str,
        configs: Mapping[str, ConfigRecord],
        search_registry_id: str,
        seed: int,
        code_commit: str,
        created_at: datetime,
    ) -> ResearchRun:
        fields: dict[str, Any] = {
            "snapshot_id": snapshot.snapshot_id,
            "protocol_id": protocol_id,
            "protocol_version": protocol_version,
            "configs": dict(configs),
            "search_registry_id": search_registry_id,
            "seed": seed,
            "code_commit": code_commit,
        }
        for slot in RUN_CONFIG_SLOTS:
            if slot not in configs:
                raise ValueError(f"missing {slot!r} config")
            fields[f"{slot}_config_hash"] = configs[slot].sha256
        identity = {k: _normalize(v) for k, v in fields.items()}
        return cls(run_id=_derived_id("run", identity), created_at=created_at, **fields)

    @model_validator(mode="after")
    def _check(self) -> ResearchRun:
        problems: list[str] = []
        missing = [s for s in RUN_CONFIG_SLOTS if s not in self.configs]
        if missing:
            problems.append(f"configs missing required slots {missing}")
        for slot in RUN_CONFIG_SLOTS:
            record = self.configs.get(slot)
            recorded = getattr(self, f"{slot}_config_hash")
            if record is not None and record.sha256 != recorded:
                problems.append(f"{slot}_config_hash does not match the embedded {slot} config")
        if not problems:
            expected = _derived_id("run", self._identity())
            if self.run_id != expected:
                problems.append(f"run_id {self.run_id!r} does not match content ({expected})")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def config_content(self, slot: str) -> dict[str, Any]:
        """The exact config content the run used (no file-system lookup)."""
        return self.configs[slot].content
