
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

If push fails, report the blocker and stop.

Never force-push.
