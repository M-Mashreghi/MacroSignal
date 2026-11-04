"""Immutable PIT snapshot builder (Task 2.13)."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from macrosignal.artifacts import ArtifactKind, ArtifactRegistry, ImmutableArtifactError
from macrosignal.domain import AvailabilityPrecision, stable_hash
from macrosignal.fixtures import load_release_stage_fixture, load_vintage_fixture
from macrosignal.pit.as_of import PitStore
from macrosignal.pit.snapshot import (
    PitSnapshot,
    build_pit_snapshot,
    current_code_commit,
    persist_pit_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
AS_OF = datetime(2026, 10, 2, 9, 0, tzinfo=NY)
CREATED = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
COMMIT = "55955cdc5acd6af6fa5a94ee89f1ba28eadf6083"
CFG = stable_hash({"config": "demo"})


def _store() -> PitStore:
    return PitStore(load_vintage_fixture() + load_release_stage_fixture())


def _build(**kw: object) -> PitSnapshot:
    args: dict[str, object] = {
        "resolver_version": "availability-resolver-1",
        "config_hash": CFG,
        "code_commit": COMMIT,
        "created_at": CREATED,
    }
    args.update(kw)
    return build_pit_snapshot(_store(), AS_OF, **args)  # type: ignore[arg-type]


def test_snapshot_contents_and_provenance() -> None:
    snap = _build()
    assert [(r.series_id, r.value) for r in snap.rows] == [
        ("GDP_LEVEL", 100.5),
        ("TEST_SERIES", 101.0),
    ]
    assert snap.source_snapshot_ids == ("fixture_release_stage", "fixture_vintage")
    assert snap.resolver_version == "availability-resolver-1"
    assert snap.config_hash == CFG and snap.code_commit == COMMIT
    assert snap.pit_snapshot_id.startswith("pit_")
    assert all(r.availability.available_at <= AS_OF for r in snap.rows)


def test_hash_is_stable_and_input_sensitive() -> None:
    a = _build()
    assert _build(created_at=datetime(2027, 1, 1, tzinfo=UTC)).pit_snapshot_id == a.pit_snapshot_id
    assert _build(code_commit="abcdef1").pit_snapshot_id != a.pit_snapshot_id
    assert _build(resolver_version="availability-resolver-2").pit_snapshot_id != a.pit_snapshot_id
    assert _build(config_hash=stable_hash({"x": 1})).pit_snapshot_id != a.pit_snapshot_id
    earlier = build_pit_snapshot(
        _store(),
        datetime(2026, 9, 15, tzinfo=NY),
        resolver_version="r",
        config_hash=CFG,
        code_commit=COMMIT,
        created_at=CREATED,
    )
    assert earlier.pit_snapshot_id != _build(resolver_version="r").pit_snapshot_id
    assert PitSnapshot.model_validate_json(a.model_dump_json()) == a


def test_tampering_and_future_rows_rejected() -> None:
    snap = _build()
    data = snap.model_dump()
    data["rows"][0]["value"] = 999.0
    with pytest.raises(ValidationError, match="does not match content"):
        PitSnapshot.model_validate(data)
    data = snap.model_dump()
    data["as_of"] = datetime(2026, 8, 1, tzinfo=NY)
    with pytest.raises(ValidationError, match="not available at as_of"):
        PitSnapshot.model_validate(data)
    data = snap.model_dump()
    data["source_snapshot_ids"] = ("other",)
    with pytest.raises(ValidationError, match="source_snapshot_ids"):
        PitSnapshot.model_validate(data)


def test_quality_report_flags_inferred_and_unknown() -> None:
    snap = _build()
    q = snap.quality
    assert q.total_rows == 2
    assert q.counts_by_precision["exact_timestamp"] == 2
    assert q.counts_by_precision["unknown"] == 0 and q.flagged == ()
    strict = _build(min_precision=AvailabilityPrecision.EXACT_TIMESTAMP)
    assert strict.quality.excluded_for_precision == ()

    eod = [
        o.model_copy(
            update={
                "availability": o.availability.model_copy(
                    update={
                        "precision": AvailabilityPrecision.INFERRED_EOD,
                        "availability_source": None,
                        "raw_available_date": None,
                    }
                )
            }
        )
        for o in load_vintage_fixture()
    ]
    flagged = build_pit_snapshot(
        PitStore(eod),
        AS_OF,
        resolver_version="r",
        config_hash=CFG,
        code_commit=COMMIT,
        created_at=CREATED,
    )
    assert flagged.quality.counts_by_precision["inferred_eod"] == 1
    assert [f.series_id for f in flagged.quality.flagged] == ["TEST_SERIES"]
    assert flagged.quality.flagged_share == 1.0
    excl = build_pit_snapshot(
        PitStore(eod),
        AS_OF,
        resolver_version="r",
        config_hash=CFG,
        code_commit=COMMIT,
        created_at=CREATED,
        min_precision=AvailabilityPrecision.RELEASE_DATE_ONLY,
    )
    assert excl.rows == () and excl.quality.excluded_for_precision == (
        "synthetic_fixture:TEST_SERIES:2026-08-01",
    )


def test_persisted_immutably(tmp_path: Path) -> None:
    reg = ArtifactRegistry(tmp_path / "data", tmp_path / "reports")
    snap = _build()
    rec = persist_pit_snapshot(reg, snap)
    assert rec.kind is ArtifactKind.PIT_SNAPSHOT
    assert (
        persist_pit_snapshot(
            reg, snap.model_copy(update={"created_at": datetime(2027, 1, 1, tzinfo=UTC)})
        )
        == rec
    )
    files = reg.read_files(snap.pit_snapshot_id)
    report = json.loads(files["quality_report.json"])
    assert report["total_rows"] == 2
    restored = PitSnapshot.model_validate(
        {**json.loads(files["snapshot.json"]), "created_at": CREATED, "quality": report}
    )
    assert restored.pit_snapshot_id == snap.pit_snapshot_id
    (reg.path_of(rec) / "snapshot.json").write_text("{}", encoding="utf-8")
    assert not reg.verify(snap.pit_snapshot_id)
    with pytest.raises(ImmutableArtifactError):
        reg.register(
            ArtifactKind.PIT_SNAPSHOT,
            snap.pit_snapshot_id,
            {"snapshot.json": b"{}"},
            created_at=CREATED,
        )


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs git")
def test_current_code_commit() -> None:
    commit = current_code_commit(ROOT)
    assert len(commit.removesuffix("-dirty")) == 40
