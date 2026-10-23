
# Point-in-Time Rules

For every decision time `t`:

```text
max(required_input.available_at) <= t
```

Preserve vintage/revision lineage.

Never:
- use the latest revised macro history as historical real-time truth,
- fit scalers/PCA/regimes using future observations,
- use an end-of-day value before it was available,
- backfill a missing historical vintage with a later revision without labeling it.
