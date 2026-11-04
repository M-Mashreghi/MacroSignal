"""Repository health / integrity checks shared by the CLI and CI.

``run_checks(root)`` returns a list of :class:`Issue` objects; any issue with
``severity == "error"`` is blocking and makes :func:`main` exit non-zero.

The structural checks use only the standard library so they can run in CI
before the package's dependencies are installed (``python
scripts/validate_project.py``).  The config-schema check needs the installed
package (pydantic / PyYAML); when those imports fail it is reported as a
warning-level skip rather than silently passing.

Checks:

* required project files exist and ``pyproject.toml`` parses;
* task ids in ``docs/PROJECT_PHASES_AND_TASKS.md`` are unique, the expected
  count, dependencies point backwards, and the ``docs/TASKS.md`` ledger lists the
  same ids with consistent completion status;
* internal Markdown links and ``configs/*.yaml`` references resolve;
* every research config (and the configs it references) validates against its
  schema;
* no secret-prone file (``.env``, keys, credentials) is tracked, and no tracked
  text file contains a credential-looking assignment or token;
* no prior-project name contamination in Markdown.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

EXPECTED_TASK_COUNT = 104

REQUIRED_FILES = (
    "CLAUDE.md",
    "README.md",
    "pyproject.toml",
    ".gitignore",
    ".env.example",
    "src/macrosignal/__init__.py",
    "src/macrosignal/cli.py",
    "scripts/validate_project.py",
    "docs/PRACTICAL_MVP.md",
    "docs/PROJECT_PHASES_AND_TASKS.md",
    "docs/TASKS.md",
    "docs/TASK_DEPENDENCIES.md",
    "docs/ARCHITECTURE.md",
    "docs/DATA_CONTRACT.md",
    "docs/AVAILABILITY_RESOLUTION.md",
    "docs/RAGGED_EDGE_POLICY.md",
    "docs/REGIME_STATE_ALIGNMENT.md",
    "docs/RETURN_AND_EXECUTION_CONTRACT.md",
    "docs/POINT_IN_TIME_POLICY.md",
    "docs/BACKTEST_POLICY.md",
    "docs/EVALUATION_PROTOCOL.md",
    "docs/GIT_WORKFLOW.md",
)

FORBIDDEN_NAMES = (
    "CaseMind",
    "CipherRoom",
    "MindForge",
    "QuizForge",
    "FedTone",
    "ImpactLens",
    "EquityDesk",
    "FilingLens",
    "RecomLab",
    "CausalImpact",
)

#: File names / suffixes that must never be tracked.
SECRET_PRONE_NAMES = re.compile(
    r"(^|/)(\.env(\.(?!example$)[^/]+)?|id_rsa|id_ed25519|\.netrc|\.pypirc"
    r"|credentials[^/]*\.json|secrets?\.(ya?ml|json|toml|txt)"
    r"|[^/]+\.(pem|key|p12|pfx|keystore))$",
    re.IGNORECASE,
)

#: Credential-looking content in tracked text files.
SECRET_CONTENT = (
    re.compile(
        r"(?i)\b[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\s*[=:]\s*['\"]?"
        r"[A-Za-z0-9/+_\-]{20,}"
    ),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".csv",
    ".json",
    ".cfg",
    ".ini",
    ".sh",
    ".example",
    "",
}

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Issue:
    check: str
    message: str
    severity: Severity = "error"

    def __str__(self) -> str:
        return f"[{self.severity}] {self.check}: {self.message}"


# --- helpers ---------------------------------------------------------------------------


def tracked_files(root: Path) -> list[str] | None:
    """Tracked paths (POSIX) via ``git ls-files``, or None outside a git checkout."""
    if not (root / ".git").exists():
        return None
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [p for p in out.decode("utf-8").split("\0") if p]


def _candidate_files(root: Path) -> list[str]:
    tracked = tracked_files(root)
    if tracked is not None:
        return tracked
    skip = {".git", ".venv", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
    out = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if p.is_file() and not (set(rel.parts) & skip) and rel.parts[0] not in {"data", "reports"}:
            out.append(rel.as_posix())
    return out


def _markdown_files(root: Path) -> list[Path]:
    return [root / p for p in _candidate_files(root) if p.endswith(".md")]


# --- checks -------------------------------------------------------------------------------


def check_required_files(root: Path) -> list[Issue]:
    issues = [
        Issue("required-files", f"missing {p}") for p in REQUIRED_FILES if not (root / p).exists()
    ]
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            issues.append(Issue("required-files", f"pyproject.toml does not parse: {exc}"))
    return issues


_TASK_HEADING = re.compile(r"^### Task (\d+\.\d+):", re.M)
_TASK_DEPS = re.compile(
    r"^### Task (\d+\.\d+):.*?\n\n\*\*Status:\*\* `\[(.)\]`.*?\n\*\*Depends on:\*\* `([^`]*)`",
    re.M | re.S,
)
_LEDGER_ROW = re.compile(r"^- \[(.)\] \*\*Task (\d+\.\d+)\*\*", re.M)


def check_tasks(root: Path, expected_count: int = EXPECTED_TASK_COUNT) -> list[Issue]:
    phases = root / "docs/PROJECT_PHASES_AND_TASKS.md"
    ledger = root / "docs/TASKS.md"
    if not phases.exists():
        return []
    text = phases.read_text(encoding="utf-8")
    ids = _TASK_HEADING.findall(text)
    issues: list[Issue] = []
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        issues.append(Issue("tasks", f"duplicate task ids {dupes}"))
    if len(ids) != expected_count:
        issues.append(Issue("tasks", f"expected {expected_count} tasks, found {len(ids)}"))

    position = {tid: i for i, tid in enumerate(ids)}
    phase_status: dict[str, str] = {}
    for tid, status, raw_deps in _TASK_DEPS.findall(text):
        phase_status[tid] = status
        if raw_deps == "None":
            continue
        for dep in (d.strip() for d in raw_deps.split(",")):
            if dep not in position:
                issues.append(Issue("tasks", f"unknown dependency {dep} for task {tid}"))
            elif position[dep] >= position[tid]:
                issues.append(Issue("tasks", f"forward/cyclic dependency {tid} -> {dep}"))
    missing_status = sorted(set(ids) - set(phase_status), key=lambda t: position[t])
    if missing_status:
        issues.append(Issue("tasks", f"tasks without parsable status/deps: {missing_status}"))

    if ledger.exists():
        rows = _LEDGER_ROW.findall(ledger.read_text(encoding="utf-8"))
        ledger_ids = [tid for _, tid in rows]
        if ledger_ids != ids:
            only_phases = sorted(set(ids) - set(ledger_ids))
            only_ledger = sorted(set(ledger_ids) - set(ids))
            issues.append(
                Issue(
                    "tasks",
                    "docs/TASKS.md ids differ from PROJECT_PHASES_AND_TASKS.md "
                    f"(missing {only_phases}, extra {only_ledger}, or order differs)",
                )
            )
        for mark, tid in rows:
            done_ledger = mark in ("x", "!")
            done_phase = phase_status.get(tid) in ("x", "!")
            if tid in phase_status and done_ledger != done_phase:
                issues.append(
                    Issue("tasks", f"task {tid} status differs between TASKS.md and phases doc")
                )
    return issues


_MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")
_CONFIG_REF = re.compile(r"configs/[A-Za-z0-9_./-]+\.ya?ml")


def check_links_and_config_refs(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for md in _markdown_files(root):
        if not md.exists():
            continue
        text = md.read_text(encoding="utf-8")
        for target in _MD_LINK.findall(text):
            file_target = target.split("#", 1)[0]
            if file_target.startswith(("http://", "https://")):
                continue
            if not (md.parent / file_target).resolve().exists():
                rel = md.relative_to(root).as_posix()
                issues.append(Issue("links", f"broken link in {rel}: {target}"))
    for rel in _candidate_files(root):
        if not rel.endswith((".md", ".yaml", ".yml")):
            continue
        path = root / rel
        if not path.exists():
            continue
        for ref in sorted(set(_CONFIG_REF.findall(path.read_text(encoding="utf-8")))):
            if not (root / ref).exists():
                issues.append(Issue("config-refs", f"unresolved config path {ref} (in {rel})"))
    return issues


def check_config_schemas(root: Path) -> list[Issue]:
    try:
        from macrosignal.config import ConfigError, load_research_config
    except ImportError as exc:  # dependencies not installed yet (bootstrap CI step)
        return [Issue("config-schema", f"skipped: {exc}", "warning")]
    issues: list[Issue] = []
    research = sorted((root / "configs/research").glob("*.y*ml"))
    if not research:
        issues.append(Issue("config-schema", "no research configs found under configs/research"))
    for path in research:
        try:
            load_research_config(path, project_root=root)
        except ConfigError as exc:
            issues.append(Issue("config-schema", str(exc).replace("\n", " | ")))
    return issues


def check_secrets(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    files = _candidate_files(root)
    for rel in files:
        if SECRET_PRONE_NAMES.search(rel):
            issues.append(Issue("secrets", f"secret-prone file is tracked: {rel}"))
    for rel in files:
        suffix = PurePosixPath(rel).suffix.lower()
        if suffix not in TEXT_SUFFIXES:
            continue
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(p.search(line) for p in SECRET_CONTENT):
                issues.append(Issue("secrets", f"credential-like content at {rel}:{lineno}"))
    example = root / ".env.example"
    if example.exists():
        for lineno, line in enumerate(example.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            if re.search(r"KEY|TOKEN|SECRET|PASSWORD", key, re.I) and value.strip():
                issues.append(Issue("secrets", f".env.example:{lineno} {key} must be empty"))
    return issues


def check_contamination(root: Path) -> list[Issue]:
    issues = []
    for md in _markdown_files(root):
        if not md.exists():
            continue
        text = md.read_text(encoding="utf-8")
        hits = sorted(name for name in FORBIDDEN_NAMES if name in text)
        if hits:
            rel = md.relative_to(root).as_posix()
            issues.append(Issue("contamination", f"prior-project names in {rel}: {hits}"))
    return issues


CHECKS: tuple[Callable[[Path], list[Issue]], ...] = (
    check_required_files,
    check_tasks,
    check_links_and_config_refs,
    check_config_schemas,
    check_secrets,
    check_contamination,
)


def run_checks(root: Path, checks: Iterable[Callable[[Path], list[Issue]]] = CHECKS) -> list[Issue]:
    issues: list[Issue] = []
    for check in checks:
        issues.extend(check(root))
    return issues


def main(root: Path | None = None, out: Callable[[str], object] = print) -> int:
    """Run all checks, print a report, and return the process exit code."""
    if root is None:
        root = Path(__file__).resolve().parents[2]
    issues = run_checks(root)
    for issue in issues:
        out(str(issue))
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        out(f"MacroSignal validation FAILED: {len(errors)} blocking issue(s).")
        return 1
    task_count = len(
        _TASK_HEADING.findall(
            (root / "docs/PROJECT_PHASES_AND_TASKS.md").read_text(encoding="utf-8")
        )
    )
    out(f"MacroSignal validation passed: {task_count} unique tasks.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
