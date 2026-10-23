"""Safe-staging guards: secrets, local environments, and raw data stay untracked."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="requires a git checkout",
)


def _is_ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", path],
        cwd=ROOT,
        check=False,
    )
    return result.returncode == 0


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        ".venv/pyvenv.cfg",
        "src/macrosignal/__pycache__/cli.cpython-311.pyc",
        "data/raw/fred/CPIAUCSL.json",
        "data/cache/http/response.json",
        "data/processed/features.parquet",
        "data/snapshots/snap_001.parquet",
        "reports/runs/run_001/manifest.json",
    ],
)
def test_sensitive_or_generated_paths_are_ignored(path: str) -> None:
    assert _is_ignored(path), f"{path} must be git-ignored"


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        "data/raw/.gitkeep",
        "reports/runs/.gitkeep",
        "configs/research/demo_daily.yaml",
    ],
)
def test_committed_templates_are_not_ignored(path: str) -> None:
    assert not _is_ignored(path), f"{path} must remain committable"


def test_no_runtime_env_file_is_tracked() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    offenders = [p for p in tracked if Path(p).name.startswith(".env") and p != ".env.example"]
    assert offenders == []
