
# Point-in-Time / No-Lookahead Policy

## Golden Rule

At simulated decision time `t`:

```text
max(required_input.available_at) <= t
```

Any violation invalidates the run.

## Real-Time Macro Data

Historical macro values may be revised.

The research system must distinguish:
- reference period,
- initial release,
- later revisions,
- latest revised history.

A historical strategy cannot silently use later revisions.

## Release Date vs Reference Period

A September macro value released in October becomes available in October, not
in September.

## End-of-Day Data

A closing or late-day Treasury observation is not available to a morning
decision on the same date.

## Feature Fitting

For:
- scalers,
- PCA,
- imputation models,
- HMM/GMM parameters,
- forecast models,
- hyperparameters,

fit only on information available up to the training cutoff.

## Backtest Guard

Before each decision:
1. collect required input rows,
2. compute their max `available_at`,
3. compare with decision time,
4. block on violation,
5. log offending source/series/row.

## Ex-Post Analysis

Future-informed:
- revised history,
- smoothed HMM probabilities,
- full-sample PCA,

may be used only in clearly labeled ex-post diagnostics.

## As-Of Query Engine (Task 2.12)

`macrosignal.pit.as_of.PitStore` keeps every vintage and release stage of each
`(source, series_id, reference_start)` (plain or resolved observations).
`as_of(t)` returns, per observation key, the vintage with the greatest
`available_at <= t`: nothing before the initial release, the initial print
until the next stage/revision becomes available, then the revision. Ties at
the same instant are ordered by stage (initial/advance < second < third <
revision < benchmark revision) and real-time start; different values at the
same instant raise `AmbiguousVintageError`. `min_precision` *excludes*
observations below the required precision (reported in
`excluded_for_precision`, never replaced by an older vintage).
`assert_no_lookahead(rows, t)` raises `LookaheadError` naming the offending
source/series/row, and every `as_of` result passes it. Timestamps must be
timezone-aware.

## PIT Snapshots (Task 2.13)

`macrosignal.pit.snapshot.build_pit_snapshot(store, as_of, ...)` freezes an
`as_of` query into a `PitSnapshot`: sorted rows, the sorted unique raw
`source_snapshot_ids`, `resolver_version`, `config_hash` and `code_commit`
(`current_code_commit()` appends `-dirty` for uncommitted changes).
`pit_snapshot_id = pit_<hash>` is a stable hash of those canonical inputs
(`created_at` excluded; durations serialize as seconds), and the validator
rejects tampered rows, rows not available at `as_of`, or mismatched source ids.
Each snapshot includes a `PrecisionQualityReport` (row counts per precision,
rows flagged as `inferred_eod` / `unknown`, rows excluded by `min_precision`).
`persist_pit_snapshot` stores `snapshot.json` and `quality_report.json` as an
immutable `pit_snapshot` artifact.
