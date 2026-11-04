"""Research protocol and hypothesis registry (Task 1.12)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from macrosignal.domain import ConfigRecord, ResearchRun, ResearchSnapshot, stable_hash
from macrosignal.protocol import (
    ProtocolIntegrityError,
    ProtocolMutationError,
    ProtocolNotFoundError,
    ProtocolRegistry,
    ProtocolStatus,
    ResearchProtocol,
)

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
COMMIT = "e3b77e4c5980649f995bab0ba4a2b570b31fb261"


def _protocol(**kw: Any) -> ResearchProtocol:
    data: dict[str, Any] = {
        "protocol_id": "H1_inflation_surprise",
        "version": 1,
        "status": "exploratory",
        "hypothesis": "Positive CPI surprises predict lower 5-day TLT returns.",
        "null_result_statement": "No robust relation after PIT controls.",
        "target": "forward_log_return",
        "horizons": ["1d", "5d"],
        "universe": ["TLT", "SPY"],
        "metrics": ["mean_abnormal_return", "t_stat_hac"],
        "primary_metric": "mean_abnormal_return",
        "sample_policy": {
            "split_method": "expanding_walk_forward",
            "development_start": date(2005, 1, 1),
            "development_end": date(2018, 12, 31),
            "test_start": date(2019, 1, 1),
            "test_end": date(2025, 12, 31),
        },
        "registered_at": T0,
    }
    data.update(kw)
    return ResearchProtocol.model_validate(data)


def _run(protocol_id: str, version: str) -> ResearchRun:
    snap = ResearchSnapshot.create(
        as_of=T0,
        input_snapshot_ids=["raw_1"],
        config_hash=stable_hash({}),
        code_commit=COMMIT,
        created_at=T0,
    )
    configs = {
        s: ConfigRecord.from_content(s, "inline", {"slot": s})
        for s in ("feature", "regime", "signal", "portfolio", "execution")
    }
    return ResearchRun.create(
        snapshot=snap,
        protocol_id=protocol_id,
        protocol_version=version,
        configs=configs,
        search_registry_id="search_1",
        seed=0,
        code_commit=COMMIT,
        created_at=T0,
    )


def test_protocol_fields_and_hash_stability() -> None:
    p = _protocol()
    assert p.status is ProtocolStatus.EXPLORATORY
    assert p.content_hash == _protocol().content_hash
    assert p.content_hash != _protocol(horizons=["1d"]).content_hash


@pytest.mark.parametrize(
    ("kw", "match"),
    [
        ({"primary_metric": "sharpe"}, "primary_metric"),
        ({"horizons": ["1d", "1d"]}, "duplicates"),
        ({"horizons": ["0d"]}, "horizons"),
        ({"metrics": []}, "metrics"),
        ({"universe": ["spy"]}, "universe"),
        (
            {
                "status": "confirmatory",
                "sample_policy": {
                    "split_method": "rolling_walk_forward",
                    "development_start": date(2005, 1, 1),
                    "development_end": date(2018, 12, 31),
                },
            },
            "held-out test window",
        ),
        (
            {
                "sample_policy": {
                    "split_method": "expanding_walk_forward",
                    "development_start": date(2005, 1, 1),
                    "development_end": date(2018, 12, 31),
                    "test_start": date(2018, 6, 1),
                    "test_end": date(2020, 1, 1),
                }
            },
            "after the development window",
        ),
    ],
)
def test_invalid_protocols_rejected(kw: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _protocol(**kw)


def test_exploratory_without_test_window_allowed() -> None:
    p = _protocol(
        sample_policy={
            "split_method": "expanding_walk_forward",
            "development_start": date(2005, 1, 1),
            "development_end": date(2018, 12, 31),
        }
    )
    assert p.sample_policy.test_start is None


def test_register_and_lookup(tmp_path: Path) -> None:
    reg = ProtocolRegistry(tmp_path)
    p1 = reg.register(_protocol())
    assert reg.register(_protocol()) == p1  # idempotent
    p2 = reg.register(_protocol(version=2, status="confirmatory"))
    assert reg.versions("H1_inflation_surprise") == [1, 2]
    assert reg.latest("H1_inflation_surprise") == p2
    assert reg.get("H1_inflation_surprise", 1) == p1
    with pytest.raises(ProtocolNotFoundError):
        reg.get("H1_inflation_surprise", 3)
    with pytest.raises(ProtocolNotFoundError):
        reg.latest("unknown")


def test_frozen_version_cannot_be_mutated(tmp_path: Path) -> None:
    reg = ProtocolRegistry(tmp_path)
    reg.register(_protocol())
    with pytest.raises(ProtocolMutationError, match="frozen"):
        reg.register(_protocol(hypothesis="Edited after seeing results."))
    assert reg.get("H1_inflation_surprise", 1).hypothesis.startswith("Positive")


def test_version_sequence_enforced(tmp_path: Path) -> None:
    reg = ProtocolRegistry(tmp_path)
    with pytest.raises(ValueError, match="must be 1"):
        reg.register(_protocol(version=2))
    reg.register(_protocol())
    with pytest.raises(ValueError, match="must be 2"):
        reg.register(_protocol(version=3))


def test_tampered_file_detected(tmp_path: Path) -> None:
    reg = ProtocolRegistry(tmp_path)
    reg.register(_protocol())
    path = reg.path_for("H1_inflation_surprise", 1)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["protocol"]["horizons"] = ["21d"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProtocolIntegrityError):
        reg.get("H1_inflation_surprise", 1)


def test_run_must_reference_frozen_protocol(tmp_path: Path) -> None:
    reg = ProtocolRegistry(tmp_path)
    reg.register(_protocol())
    assert reg.require_for_run(_run("H1_inflation_surprise", "1")).version == 1
    with pytest.raises(ProtocolNotFoundError):
        reg.require_for_run(_run("H1_inflation_surprise", "2"))
    with pytest.raises(ProtocolNotFoundError, match="not a registered version"):
        reg.require_for_run(_run("H1_inflation_surprise", "latest"))
