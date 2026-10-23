
# Git & GitHub Workflow

Every task must create one auditable commit and push before the next task.

## Start

```bash
git status --short
git branch --show-current
git remote -v
```

Do not absorb unrelated changes.

## Before Commit

1. run task tests,
2. run PIT/leakage checks if applicable,
3. update task docs,
4. run:

```bash
git diff --check
git status --short
git diff --stat
```

5. stage only task-related files.

## Safe Staging

Stage explicit paths only. Do not use `git add -A`, `git add .`, or
`git commit -a`, which can absorb unrelated user changes.

```bash
git add <path> [<path> ...]
git diff --cached --name-only   # must list only this task's files
```

Before committing, confirm none of the staged paths is:

- a runtime `.env` / `.env.*` file (only `.env.example` is committed),
- a local environment or cache (`.venv/`, `__pycache__/`, tool caches),
- raw, cached, processed, or snapshot data under `data/` (only `.gitkeep`),
- generated run output under `reports/` (only `.gitkeep`),
- an API key, token, or other credential in any file.

`tests/unit/test_git_hygiene.py` checks that `.gitignore` keeps these paths
untracked and that no runtime `.env` file is tracked.

## Remote Policy

- Use the existing `origin`; never invent, add, or replace a remote without
  explicit approval.
- If the folder is not yet a git repository, `git init -b main` and report that
  `origin` is missing; do not add one.
- Only push when `origin` exists and authentication already works.

Verified baseline (Task 1.2): branch `main`, `origin` =
`https://github.com/M-Mashreghi/MacroSignal.git`, upstream `origin/main`,
HTTPS push authentication working.

## Commit

```text
task(<task-id>): <short imperative summary>
```

## Push

```bash
git push
```

If there is no upstream and `origin` is already correct:

```bash
git push -u origin HEAD
```

## Verify

```bash
git status -sb
git log -1 --oneline
git rev-parse HEAD
git rev-parse @{u}
```

`HEAD` and `@{u}` must be identical.

If push fails, keep the verified local commit, mark the task `[!]` in
`docs/TASKS.md`, report the blocker, and stop.

Never force-push or rewrite already-pushed history.

## Recording Commit Hashes

A commit cannot contain its own hash. The task commit therefore sets the
ledger entry in `docs/TASKS.md` to `Commit: pending`. After the push is
verified, the short hash and push status are recorded in the next task's
commit, or, when no further task follows in the same session, in a separate
`docs(tasks): record task <task-id> commit hash` commit that is pushed and
verified the same way.
