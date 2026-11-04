"""Repository validation CLI and health checks (Task 1.13)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from macrosignal.cli import app
from macrosignal.validation import (
    REQUIRED_FILES,
    check_contamination,
    check_links_and_config_refs,
    check_required_files,
    check_secrets,
    check_tasks,
    main,
    run_checks,
)

ROOT = Path(__file__).resolve().parents[2]


def test_repository_passes() -> None:
    errors = [i for i in run_checks(ROOT) if i.severity == "error"]
    assert errors == []
    lines: list[str] = []
    assert main(ROOT, out=lines.append) == 0
    assert "104 unique tasks" in lines[-1]


def test_script_exit_code() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_project.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_cli_command() -> None:
    result = CliRunner().invoke(app, ["validate", "--root", str(ROOT)])
    assert result.exit_code == 0, result.output
    assert "validation passed" in result.output


def _mini_repo(tmp_path: Path) -> Path:
    for rel in REQUIRED_FILES:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("x\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (tmp_path / ".env.example").write_text("FRED_API_KEY=\n", encoding="utf-8")
    (tmp_path / "docs/PROJECT_PHASES_AND_TASKS.md").write_text(
        "### Task 1.1: A\n\n**Status:** `[x]` Completed\\\n**Depends on:** `None`\n\n"
        "### Task 1.2: B\n\n**Status:** `[ ]` Not Started  \n**Depends on:** `1.1`\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/TASKS.md").write_text(
        "- [x] **Task 1.1** — A\n- [ ] **Task 1.2** — B\n", encoding="utf-8"
    )
    return tmp_path


def test_missing_required_file_and_bad_toml(tmp_path: Path) -> None:
    repo = _mini_repo(tmp_path)
    assert check_required_files(repo) == []
    (repo / "docs/GIT_WORKFLOW.md").unlink()
    (repo / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    messages = [i.message for i in check_required_files(repo)]
    assert any("GIT_WORKFLOW" in m for m in messages)
    assert any("does not parse" in m for m in messages)


def test_task_checks(tmp_path: Path) -> None:
    repo = _mini_repo(tmp_path)
    assert check_tasks(repo, expected_count=2) == []
    phases = repo / "docs/PROJECT_PHASES_AND_TASKS.md"
    text = phases.read_text(encoding="utf-8")
    phases.write_text(text + "\n### Task 1.2: dup\n", encoding="utf-8")
    assert any("duplicate" in i.message for i in check_tasks(repo, expected_count=3))
    phases.write_text(text.replace("`1.1`", "`1.3`"), encoding="utf-8")
    assert any("unknown dependency" in i.message for i in check_tasks(repo, expected_count=2))
    phases.write_text(text, encoding="utf-8")
    (repo / "docs/TASKS.md").write_text(
        "- [ ] **Task 1.1** — A\n- [ ] **Task 1.2** — B\n", encoding="utf-8"
    )
    assert any("status differs" in i.message for i in check_tasks(repo, expected_count=2))
    (repo / "docs/TASKS.md").write_text("- [x] **Task 1.1** — A\n", encoding="utf-8")
    assert any("ids differ" in i.message for i in check_tasks(repo, expected_count=2))


def test_unresolved_links_and_config_paths(tmp_path: Path) -> None:
    repo = _mini_repo(tmp_path)
    (repo / "README.md").write_text(
        "See [x](docs/MISSING.md) and configs/research/nope.yaml\n", encoding="utf-8"
    )
    checks = {i.check for i in check_links_and_config_refs(repo)}
    assert checks == {"links", "config-refs"}


@pytest.mark.parametrize(
    "rel", [".env", ".env.local", "keys/server.pem", "credentials-prod.json", "secrets.yaml"]
)
def test_secret_prone_files_detected(tmp_path: Path, rel: str) -> None:
    repo = _mini_repo(tmp_path)
    dest = repo / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("placeholder\n", encoding="utf-8")
    assert any("secret-prone" in i.message for i in check_secrets(repo))


@pytest.mark.parametrize(
    "line",
    [
        "FRED_API_KEY=" + "a" * 32,
        'token: "' + "Z9" * 15 + '"',
        "gh" + "p_" + "A" * 36,
        "-----BEGIN RSA " + "PRIVATE KEY-----",
    ],
)
def test_credential_content_detected(tmp_path: Path, line: str) -> None:
    repo = _mini_repo(tmp_path)
    (repo / "notes.txt").write_text(line + "\n", encoding="utf-8")
    assert any("credential-like" in i.message for i in check_secrets(repo))


def test_env_example_values_must_be_empty(tmp_path: Path) -> None:
    repo = _mini_repo(tmp_path)
    assert check_secrets(repo) == []
    (repo / ".env.example").write_text("BEA_API_KEY=abc\n", encoding="utf-8")
    assert any("must be empty" in i.message for i in check_secrets(repo))


def test_contamination(tmp_path: Path) -> None:
    repo = _mini_repo(tmp_path)
    (repo / "README.md").write_text("copied from " + "Fed" + "Tone\n", encoding="utf-8")
    assert check_contamination(repo)


def test_main_returns_nonzero_on_blocking_issue(tmp_path: Path) -> None:
    repo = _mini_repo(tmp_path)
    shutil.copytree(ROOT / "configs", repo / "configs")
    (repo / ".env").write_text("X=1\n", encoding="utf-8")
    lines: list[str] = []
    assert main(repo, out=lines.append) == 1
    assert "FAILED" in lines[-1]
