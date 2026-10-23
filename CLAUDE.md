
# MacroSignal — Claude Code Instructions

MacroSignal is a point-in-time U.S. macro regime, event-study, and cross-asset
research platform.

The quality of this project is determined primarily by chronology, provenance,
and research honesty — not model complexity.

## Read Before Every Task

Read, in order:

1. `docs/PROJECT_PHASES_AND_TASKS.md`
2. `docs/PRACTICAL_MVP.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DATA_CONTRACT.md`
5. `docs/AVAILABILITY_RESOLUTION.md`
6. `docs/POINT_IN_TIME_POLICY.md`
7. `docs/RAGGED_EDGE_POLICY.md`
8. `docs/EXPECTATIONS_AND_SURPRISES.md`
9. `docs/REGIME_MODELING.md`
10. `docs/REGIME_STATE_ALIGNMENT.md`
11. `docs/RETURN_AND_EXECUTION_CONTRACT.md`
12. `docs/BACKTEST_POLICY.md`
13. `docs/EVALUATION_PROTOCOL.md`
14. `docs/GIT_WORKFLOW.md`
15. `docs/FINAL_AUDIT.md`
16. applicable `.claude/rules/*.md`

Do not invent requirements that conflict with these documents.

## Mandatory Per-Task Workflow

For every task:

1. Read the exact task, dependency, contract, and Definition of Done.
2. Inspect:
   ```bash
   git status --short
   git branch --show-current
   git remote -v
   ```
3. Implement only the requested task.
4. Add/update deterministic tests or fixtures.
5. Run task-specific validation.
6. Run point-in-time / leakage checks when applicable.
7. Fix all blocking failures.
8. Update:
   - `docs/TASKS.md`
   - `docs/PROJECT_PHASES_AND_TASKS.md`
9. Run:
   ```bash
   git diff --check
   git status --short
   git diff --stat
   ```
10. Stage only task-related files.
11. Commit:
    ```text
    task(<task-id>): <short imperative summary>
    ```
12. Push to GitHub.
13. Verify upstream matches local HEAD.
14. STOP.

Do not automatically begin the next task.

## Git Safety

Never:
- force-push,
- invent a repository URL,
- replace `origin` without explicit approval,
- commit secrets,
- commit proprietary/raw licensed data,
- absorb unrelated user changes,
- rewrite already-pushed history,
- claim a push succeeded without verification.

If push authentication fails:
- keep the verified local commit,
- mark the task `[!]`,
- report the blocker,
- stop.

## Point-in-Time Golden Rule

At every simulated decision timestamp `t`:

```text
max(required_input.available_at) <= t
```

Any violation blocks the research run.

Preserve:
- source,
- source series/release id,
- reference period,
- release stage,
- release timestamp,
- availability timestamp,
- availability precision,
- vintage / real-time period,
- retrieval timestamp,
- raw snapshot id,
- adapter version.

## Availability Precision

Do not pretend a date-only source gives an exact timestamp.

Use explicit precision such as:

```text
exact_timestamp
release_date_only
inferred_eod
provider_timestamp
unknown
```

When a series has date-level ALFRED vintage metadata but an official BLS/BEA/Fed
release schedule supplies an exact release time, the resolver may combine them
only through a documented mapping.

## Ragged-Edge Macro Rule

A daily macro state contains observations with different ages and release
frequencies.

Never blindly forward-fill and then treat every feature as equally fresh.

For each feature expose:
- value,
- available_at,
- reference period,
- age since availability,
- age since reference period,
- stale flag,
- availability precision.

The model may use the last-known value only under an explicit staleness policy.

## Expectations / Surprise Rule

Keep these concepts separate:

### Market surprise
Requires a real pre-release consensus/expectation record.

### Forecast error
Uses a model forecast created before release.

Do not relabel model forecast error as market surprise.

If no valid expectation exists:
- market surprise is missing,
- do not fabricate one.

## Macro Transformation Rule

Every derived macro feature must declare:
- input series,
- transformation,
- units,
- seasonal adjustment,
- lag,
- publication availability,
- fit window if statistical.

Examples:
- YoY percent,
- MoM percent,
- annualized QoQ,
- level difference,
- rolling z-score.

Never mix transformation conventions silently.

## Regime Integrity

### HMM
- filtered probabilities: contemporaneous and allowed,
- smoothed probabilities: future-informed and ex-post only.

### GMM / HMM state IDs
State indices are arbitrary.

After every walk-forward refit, states must be aligned to stable canonical
economic identities before signals use them.

Never assume `state_0` means the same economic regime across refits.

### PCA / scalers / clustering
Fit only on the training/history window.

## Event-Study Integrity

Every event study declares:
- event timestamp,
- event-time precision,
- release stage,
- market-data frequency,
- price convention,
- event window,
- sample size,
- overlap/contamination status.

Do not claim intraday effects from daily data.

## Return / Asset Integrity

Every asset must declare:
- tradable start/end dates,
- data field,
- split/dividend adjustment policy,
- currency,
- provider,
- timezone,
- return convention.

Do not backfill an ETF before its inception.

Cash / uninvested capital must have an explicit return assumption.

## Execution Integrity

Separate:
- information time,
- signal time,
- decision time,
- execution time,
- mark-to-market time.

A daily backtest must use an explicit execution preset.

Never use a price that was not available at the simulated execution time.

## Backtest Integrity

Mandatory:
- chronological / walk-forward splits,
- no revised-data leakage,
- no future preprocessing,
- no future state smoothing,
- no test-set tuning,
- explicit costs,
- explicit turnover,
- explicit cash return,
- benchmark comparison,
- gross and net results.

## Research Selection Integrity

Every tested configuration must be registered.

Do not present only the highest Sharpe without recording:
- number of variants tried,
- assets,
- horizons,
- regime models,
- signal variants,
- parameter ranges.

## LLM Boundary

LLMs may:
- summarize already-validated release text,
- structure qualitative policy themes,
- draft commentary from deterministic results.

LLMs may not:
- fabricate observations,
- compute canonical returns,
- compute portfolio weights,
- validate chronology,
- overwrite statistical outputs,
- infer unavailable consensus values.

## Practicality Rule

Prefer a defensible daily U.S. macro research platform over premature complexity.

v1 priorities:
- official primary macro data,
- PIT reconstruction,
- release-aware daily research,
- transparent expectation modes,
- ragged-edge features,
- stable regime identities,
- honest event studies,
- simple portfolios,
- walk-forward backtests,
- decision audit trail.

Defer:
- live trading,
- global macro,
- proprietary data dependencies,
- high-frequency execution,
- complex neural forecasting,
- derivatives,
- institutional OMS/risk systems.

## Completion Rule

A task is complete only when:
1. implementation exists,
2. required tests pass,
3. chronology / PIT checks pass where applicable,
4. docs are synchronized,
5. one task-scoped commit exists,
6. GitHub push succeeds and is verified when `origin` exists,
7. Claude stops.
