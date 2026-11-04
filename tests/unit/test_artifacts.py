"""Artifact registry and storage layout (Task 1.10)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from macrosignal.artifacts import (
    ArtifactKind,
    ArtifactNotFoundError,
    ArtifactRegistry,
    ImmutableArtifactError,
    content_hash,
    dump_json_bytes,
)

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def reg(tmp_path: Path) -> ArtifactRegistry:
    return ArtifactRegistry(tmp_path / "data", tmp_path / "reports")


@pytest.mark.parametrize(
    ("kind", "source", "expected"),
    [
        (ArtifactKind.RAW_SNAPSHOT, "fred", ("data", "raw/fred/a1")),
        (ArtifactKind.PIT_SNAPSHOT, None, ("data", "snapshots/pit/a1")),
        (ArtifactKind.FEATURES, None, ("data", "processed/features/a1")),
        (ArtifactKind.MODEL_FIT, None, ("data", "processed/model_fits/a1")),
        (ArtifactKind.BACKTEST, None, ("reports", "runs/a1/backtest")),
        (ArtifactKind.REPORT, None, ("reports", "runs/a1/report")),
    ],
)
def test_layout_is_deterministic(
    kind: ArtifactKind, source: str | None, expected: tuple[str, str]
) -> None:
    assert ArtifactRegistry.layout(kind, "a1", source) == expected


@pytest.mark.parametrize("bad", ["../x", "a/b", "", ".hidden", "a b", "C:x"])
def test_unsafe_ids_rejected(reg: ArtifactRegistry, bad: str) -> None:
    with pytest.raises(ValueError, match="unsafe"):
        reg.path_for(ArtifactKind.FEATURES, bad)


def test_unsafe_file_names_rejected(reg: ArtifactRegistry) -> None:
    for name in ("../escape.txt", "/abs.txt", "a\\b.txt"):
        with pytest.raises(ValueError, match="unsafe artifact file path"):
            reg.register(ArtifactKind.FEATURES, "f1", {name: b"x"}, created_at=T0)


def test_raw_snapshot_requires_source(reg: ArtifactRegistry) -> None:
    with pytest.raises(ValueError, match="source"):
        reg.register(ArtifactKind.RAW_SNAPSHOT, "r1", {"a.json": b"{}"}, created_at=T0)


def test_register_write_and_lookup(reg: ArtifactRegistry) -> None:
    raw = reg.register(
        ArtifactKind.RAW_SNAPSHOT,
        "raw_fred_001",
        {"payload.json": b"{}"},
        created_at=T0,
        source="fred",
    )
    pit = reg.register(
        ArtifactKind.PIT_SNAPSHOT,
        "snap_abc",
        {"manifest.json": dump_json_bytes({"a": 1})},
        created_at=T0,
        snapshot_id="snap_abc",
    )
    fit = reg.register(
        ArtifactKind.MODEL_FIT,
        "fit_hmm_001",
        {"params.json": b"{}", "states/map.json": b"[]"},
        created_at=T0,
        snapshot_id="snap_abc",
        run_id="run_1",
    )
    bt = reg.register(
        ArtifactKind.BACKTEST,
        "run_1",
        {"returns.csv": b"d,r\n"},
        created_at=T0,
        run_id="run_1",
        snapshot_id="snap_abc",
        model_fit_id="fit_hmm_001",
    )
    assert reg.path_of(raw) == reg.data_dir / "raw/fred/raw_fred_001"
    assert (reg.path_of(fit) / "states/map.json").read_bytes() == b"[]"
    assert reg.get("snap_abc") == pit
    assert {r.artifact_id for r in reg.by_run("run_1")} == {"fit_hmm_001", "run_1"}
    assert {r.artifact_id for r in reg.by_snapshot("snap_abc")} == {
        "snap_abc",
        "fit_hmm_001",
        "run_1",
    }
    assert {r.artifact_id for r in reg.by_model_fit("fit_hmm_001")} == {"fit_hmm_001", "run_1"}
    assert fit.model_fit_id == "fit_hmm_001"
    assert bt.files == ("returns.csv",)
    assert reg.verify("run_1")
    with pytest.raises(ArtifactNotFoundError):
        reg.get("missing")


def test_identical_reregistration_is_idempotent(reg: ArtifactRegistry) -> None:
    first = reg.register(ArtifactKind.FEATURES, "f1", {"x.csv": b"1"}, created_at=T0)
    again = reg.register(
        ArtifactKind.FEATURES, "f1", {"x.csv": b"1"}, created_at=datetime(2027, 1, 1, tzinfo=UTC)
    )
    assert again == first
    assert len(reg.records()) == 1


def test_different_content_never_overwrites(reg: ArtifactRegistry) -> None:
    reg.register(ArtifactKind.FEATURES, "f1", {"x.csv": b"1"}, created_at=T0)
    with pytest.raises(ImmutableArtifactError, match="different content"):
        reg.register(ArtifactKind.FEATURES, "f1", {"x.csv": b"2"}, created_at=T0)
    with pytest.raises(ImmutableArtifactError, match="different kind"):
        reg.register(ArtifactKind.MODEL_FIT, "f1", {"x.csv": b"1"}, created_at=T0)
    assert reg.read_files("f1") == {"x.csv": b"1"}


def test_unregistered_existing_directory_not_overwritten(reg: ArtifactRegistry) -> None:
    target = reg.path_for(ArtifactKind.FEATURES, "f2")
    target.mkdir(parents=True)
    with pytest.raises(ImmutableArtifactError, match="unregistered files"):
        reg.register(ArtifactKind.FEATURES, "f2", {"x.csv": b"1"}, created_at=T0)


def test_verify_detects_tampering(reg: ArtifactRegistry) -> None:
    rec = reg.register(ArtifactKind.REPORT, "run_9", {"r.md": b"hello"}, created_at=T0)
    (reg.path_of(rec) / "r.md").write_bytes(b"edited")
    assert not reg.verify("run_9")
    (reg.path_of(rec) / "r.md").unlink()
    assert not reg.verify("run_9")


def test_content_hash_independent_of_insertion_order() -> None:
    assert content_hash({"a": b"1", "b": b"2"}) == content_hash({"b": b"2", "a": b"1"})
    assert content_hash({"a": b"1"}) != content_hash({"a": b"2"})


def test_registry_persists_across_instances(tmp_path: Path) -> None:
    ArtifactRegistry(tmp_path / "d", tmp_path / "r").register(
        ArtifactKind.FEATURES, "f1", {"x.csv": b"1"}, created_at=T0
    )
    assert ArtifactRegistry(tmp_path / "d", tmp_path / "r").get("f1").kind is ArtifactKind.FEATURES


def test_registry_location_is_git_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/registry/*" in gitignore
