"""ResearchSnapshot / ResearchRun manifests and stable hashing (Task 1.9)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import yaml
from pydantic import ValidationError

from macrosignal.domain import (
    RUN_CONFIG_SLOTS,
    ConfigRecord,
    ResearchRun,
    ResearchSnapshot,
    canonical_json,
    stable_hash,
)

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
COMMIT = "c53a78afff82a34d8c6d303e91f4a6dbed231fc2"


def test_canonical_json_is_order_and_timezone_stable() -> None:
    a = {"b": 1, "a": [1.5, "x"], "t": datetime(2026, 10, 15, 8, 30, tzinfo=NY)}
    b = {"t": datetime(2026, 10, 15, 12, 30, tzinfo=UTC), "a": (1.5, "x"), "b": 1}
    assert canonical_json(a) == canonical_json(b)
    assert canonical_json(a) == '{"a":[1.5,"x"],"b":1,"t":"2026-10-15T12:30:00+00:00"}'
    assert stable_hash(a) == stable_hash(b)
    assert stable_hash({"d": date(2026, 1, 2)}).startswith("sha256:")
    assert canonical_json({"dt": timedelta(hours=1, seconds=1)}) == '{"dt":3601.0}'


@pytest.mark.parametrize(
    "bad", [{"x": float("nan")}, {"x": datetime(2026, 1, 1)}, {1: "a"}, {"x": object()}]
)
def test_canonical_json_rejects_unstable_values(bad: Any) -> None:
    with pytest.raises((ValueError, TypeError)):
        canonical_json(bad)


def test_known_hash_is_pinned() -> None:
    # Guards against accidental changes to the serialization format.
    assert stable_hash({"a": 1}) == (
        "sha256:015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"
    )


def _snapshot(**kw: Any) -> ResearchSnapshot:
    data: dict[str, Any] = {
        "as_of": datetime(2026, 10, 31, 21, 0, tzinfo=UTC),
        "input_snapshot_ids": ["raw_fred_002", "raw_bls_001"],
        "config_hash": stable_hash({"cfg": 1}),
        "code_commit": COMMIT,
        "created_at": datetime(2026, 11, 1, 9, 0, tzinfo=UTC),
    }
    data.update(kw)
    return ResearchSnapshot.create(**data)


def test_snapshot_id_is_deterministic_and_excludes_created_at() -> None:
    s1 = _snapshot()
    s2 = _snapshot(
        input_snapshot_ids=["raw_bls_001", "raw_fred_002"],
        created_at=datetime(2026, 11, 2, tzinfo=UTC),
    )
    assert s1.snapshot_id == s2.snapshot_id
    assert s1.input_snapshot_ids == ("raw_bls_001", "raw_fred_002")
    assert _snapshot(code_commit="abcdef1").snapshot_id != s1.snapshot_id
    assert ResearchSnapshot.model_validate_json(s1.model_dump_json()) == s1


def test_snapshot_rejects_tampering_and_future() -> None:
    s = _snapshot()
    data = s.model_dump()
    data["config_hash"] = stable_hash({"cfg": 2})
    with pytest.raises(ValidationError, match="does not match content"):
        ResearchSnapshot.model_validate(data)
    with pytest.raises(ValidationError, match="cannot contain the future"):
        _snapshot(created_at=datetime(2026, 10, 1, tzinfo=UTC))
    with pytest.raises(ValidationError, match="code_commit"):
        _snapshot(code_commit="main")
    with pytest.raises(ValidationError, match="not be empty"):
        _snapshot(input_snapshot_ids=[])
    with pytest.raises(ValidationError):
        s.as_of = datetime(2026, 1, 1, tzinfo=UTC)  # type: ignore[misc]


def _configs() -> dict[str, ConfigRecord]:
    regimes = yaml.safe_load((ROOT / "configs/regimes/regimes_v1.yaml").read_text("utf-8"))
    signals = yaml.safe_load((ROOT / "configs/signals/signals_v1.yaml").read_text("utf-8"))
    return {
        "feature": ConfigRecord.from_content("feature", "inline", {"version": 1}),
        "regime": ConfigRecord.from_content("regime", "configs/regimes/regimes_v1.yaml", regimes),
        "signal": ConfigRecord.from_content("signal", "configs/signals/signals_v1.yaml", signals),
        "portfolio": ConfigRecord.from_content("portfolio", "inline", {"max_weight": 0.4}),
        "execution": ConfigRecord.from_content(
            "execution", "inline", {"preset": "next_session_close", "cash": "zero"}
        ),
    }


def _run(**kw: Any) -> ResearchRun:
    data: dict[str, Any] = {
        "snapshot": _snapshot(),
        "protocol_id": "H1_inflation_surprise",
        "protocol_version": "1",
        "configs": _configs(),
        "search_registry_id": "search_001",
        "seed": 7,
        "code_commit": COMMIT,
        "created_at": datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
    }
    data.update(kw)
    return ResearchRun.create(**data)


def test_run_round_trip_and_deterministic_id() -> None:
    r1 = _run()
    r2 = _run(created_at=datetime(2026, 12, 1, tzinfo=timezone(timedelta(hours=1))))
    assert r1.run_id == r2.run_id
    assert r1.run_id.startswith("run_")
    assert _run(seed=8).run_id != r1.run_id
    restored = ResearchRun.model_validate_json(r1.to_canonical_json())
    assert restored == r1
    assert restored.manifest_hash == r1.manifest_hash
    assert restored.regime_config_hash == r1.configs["regime"].sha256


def test_run_auditable_without_config_files(tmp_path: Path) -> None:
    run = _run()
    stored = tmp_path / "run.json"
    stored.write_text(run.to_canonical_json(), encoding="utf-8")
    restored = ResearchRun.model_validate_json(stored.read_text(encoding="utf-8"))
    # Content is embedded; no lookup of the (mutable) YAML files is required.
    assert restored.config_content("execution") == {"preset": "next_session_close", "cash": "zero"}
    assert set(RUN_CONFIG_SLOTS) <= set(restored.configs)


def test_run_rejects_mismatched_or_missing_configs() -> None:
    with pytest.raises(ValueError, match="missing 'portfolio'"):
        _run(configs={k: v for k, v in _configs().items() if k != "portfolio"})
    data = _run().model_dump()
    data["signal_config_hash"] = stable_hash({"other": True})
    with pytest.raises(ValidationError, match="signal_config_hash does not match"):
        ResearchRun.model_validate(data)
    data = _run().model_dump()
    data["seed"] = 99
    with pytest.raises(ValidationError, match="run_id"):
        ResearchRun.model_validate(data)


def test_config_record_detects_edited_content() -> None:
    rec = ConfigRecord.from_content("x", "inline", {"a": 1})
    data = rec.model_dump()
    data["content"] = {"a": 2}
    with pytest.raises(ValidationError, match="content hash"):
        ConfigRecord.model_validate(data)
