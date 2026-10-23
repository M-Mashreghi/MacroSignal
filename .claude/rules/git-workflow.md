
# Git / GitHub Workflow Rules

Every completed task:

```text
Implement
→ Test
→ PIT / leakage checks
→ Update docs
→ git diff --check
→ Stage task files only
→ Commit
→ Push
→ Verify upstream
→ STOP
```

Commit format:

```text
task(<task-id>): <short imperative summary>
```

Never force-push, invent/change origin, commit secrets, or absorb unrelated work.
