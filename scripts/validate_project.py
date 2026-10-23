from __future__ import annotations

from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]

required = [
    "CLAUDE.md",
    "README.md",
    "pyproject.toml",
    "src/macrosignal/__init__.py",
    "src/macrosignal/cli.py",
    "docs/PRACTICAL_MVP.md",
    "docs/PROJECT_PHASES_AND_TASKS.md",
    "docs/TASK_DEPENDENCIES.md",
    "docs/AVAILABILITY_RESOLUTION.md",
    "docs/RAGGED_EDGE_POLICY.md",
    "docs/REGIME_STATE_ALIGNMENT.md",
    "docs/RETURN_AND_EXECUTION_CONTRACT.md",
    "docs/POINT_IN_TIME_POLICY.md",
    "docs/BACKTEST_POLICY.md",
    "docs/GIT_WORKFLOW.md",
]
missing = [p for p in required if not (ROOT / p).exists()]
if missing:
    print("Missing required project files:", missing)
    sys.exit(1)

# TOML parse check.
with (ROOT / "pyproject.toml").open("rb") as f:
    tomllib.load(f)

# Task IDs, order, and dependencies.
task_text = (ROOT / "docs/PROJECT_PHASES_AND_TASKS.md").read_text(encoding="utf-8")
task_ids = re.findall(r"^### Task (\d+\.\d+):", task_text, flags=re.M)
if len(task_ids) != len(set(task_ids)):
    print("Duplicate task IDs found.")
    sys.exit(1)
if len(task_ids) != 104:
    print(f"Expected 104 tasks in FINAL package; found {len(task_ids)}.")
    sys.exit(1)

position = {task_id: i for i, task_id in enumerate(task_ids)}
dep_pattern = re.compile(
    r"^### Task (\d+\.\d+):.*?\n\n\*\*Status:\*\*.*?\n\*\*Depends on:\*\* `([^`]*)`",
    flags=re.M | re.S,
)
for match in dep_pattern.finditer(task_text):
    task_id, raw_deps = match.groups()
    if raw_deps == "None":
        continue
    for dep in [x.strip() for x in raw_deps.split(",")]:
        if dep not in position:
            print(f"Unknown dependency {dep} for task {task_id}.")
            sys.exit(1)
        if position[dep] >= position[task_id]:
            print(f"Forward/cyclic dependency {task_id} -> {dep}.")
            sys.exit(1)

# Internal Markdown file links.
link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")
for md in ROOT.rglob("*.md"):
    text = md.read_text(encoding="utf-8")
    for target in link_pattern.findall(text):
        file_target = target.split("#", 1)[0]
        if file_target.startswith(("http://", "https://")):
            continue
        resolved = (md.parent / file_target).resolve()
        if not resolved.exists():
            print(f"Broken Markdown link in {md.relative_to(ROOT)}: {target}")
            sys.exit(1)

# Check every referenced committed config path exists.
config_ref_pattern = re.compile(r"configs/[A-Za-z0-9_./-]+\.ya?ml")
for path in list(ROOT.rglob("*.md")) + list(ROOT.rglob("*.yaml")):
    text = path.read_text(encoding="utf-8")
    for ref in set(config_ref_pattern.findall(text)):
        if not (ROOT / ref).exists():
            print(f"Missing referenced config {ref} (from {path.relative_to(ROOT)}).")
            sys.exit(1)

# Prevent common project-name contamination.
forbidden = {
    "CaseMind", "CipherRoom", "MindForge", "QuizForge", "FedTone",
    "ImpactLens", "EquityDesk", "FilingLens", "RecomLab", "CausalImpact",
}
for md in ROOT.rglob("*.md"):
    text = md.read_text(encoding="utf-8")
    hits = sorted(name for name in forbidden if name in text)
    if hits:
        print(f"Prior-project contamination in {md.relative_to(ROOT)}: {hits}")
        sys.exit(1)

# No committed runtime .env.
if (ROOT / ".env").exists():
    print("Committed .env is forbidden.")
    sys.exit(1)

print(f"MacroSignal FINAL validation passed: {len(task_ids)} unique tasks.")
