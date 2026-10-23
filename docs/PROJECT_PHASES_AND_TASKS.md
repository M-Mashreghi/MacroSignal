# MacroSignal — Project Phases & Atomic Tasks

**Single source of truth** for implementation scope and completion.

Status: `[ ]` Not Started · `[-]` In Progress · `[x]` Completed · `[!]` Push Blocked

## Global Definition of Done

Every task must satisfy:

1. Task-specific implementation exists.
2. Required validation passes.
3. Point-in-time and release-time chronology remain correct.
4. Availability precision is not overstated.
5. Ragged-edge freshness/staleness remains visible.
6. No future revisions, transforms, state smoothing, model fits, or test data leak backward.
7. Regime state identities are aligned before strategy use.
8. Asset lifecycle and return/execution contracts remain valid.
9. Market surprise and model forecast error remain correctly labeled.
10. Costs, turnover, and cash assumptions are explicit in backtest changes.
11. Documentation is synchronized.
12. `git diff --check` passes.
13. One task-scoped commit exists.
14. GitHub push succeeds and is verified when `origin` is configured.
15. Claude stops after the task.

---

## Phase 1 — Foundation, Reproducibility & Research Protocol

### Task 1.1: Complete Python Package Scaffold & Development Tooling

**Status:** `[x]` Completed\
**Depends on:** `None`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Complete and verify the pre-seeded installable src-layout package, test layout, and development tooling defined by the repository skeleton.
- Make editable installation, `macrosignal version`, and a smoke import work without implementing research logic.
- Add the first package-level smoke test while preserving the minimal bootstrap CLI.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [x] Task-specific implementation exists.
- [x] Relevant automated validation passes.
- [x] PIT / chronology invariants pass where applicable.
- [x] Research provenance is preserved.
- [x] Documentation and task status are synchronized.
- [x] A dedicated `task(1.1): ...` commit exists.
- [x] Commit is pushed and upstream is verified when `origin` is configured.
- [x] Claude stops before the next task.

---
### Task 1.2: GitHub Remote & Per-Task Commit Workflow Baseline

**Status:** `[x]` Completed\
**Depends on:** `1.1`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Inspect branch, working tree, and existing `origin`; never invent or replace a remote.
- Verify the per-task commit/push procedure and safe staging behavior.
- Only test a push when authentication and a correct remote already exist.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [x] Task-specific implementation exists.
- [x] Relevant automated validation passes.
- [x] PIT / chronology invariants pass where applicable.
- [x] Research provenance is preserved.
- [x] Documentation and task status are synchronized.
- [x] A dedicated `task(1.2): ...` commit exists.
- [x] Commit is pushed and upstream is verified when `origin` is configured.
- [x] Claude stops before the next task.

---
### Task 1.3: Typed Configuration Loader & Environment Separation

**Status:** `[ ]` Not Started  
**Depends on:** `1.2`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Load YAML research/config files into typed validated configuration objects.
- Keep secrets/environment overrides separate from committed research configs.
- Reject unknown critical fields and invalid file references with actionable errors.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.3): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.4: MacroObservation Domain Model

**Status:** `[ ]` Not Started  
**Depends on:** `1.3`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement the canonical macro observation including reference period, units, release family/stage, vintage lineage, and source metadata.
- Require an AvailabilityStamp rather than a naive availability date.
- Validate impossible reference/release relationships and unsupported precision values.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.4): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.5: AvailabilityStamp & ReleaseEvent Domain Models

**Status:** `[ ]` Not Started  
**Depends on:** `1.4`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement explicit availability precision and provenance plus timezone-aware release events.
- Represent scheduled and actual release time separately.
- Prevent naive timestamps from entering the canonical domain.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.5): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.6: ExpectationObservation & Forecast Provenance Models

**Status:** `[ ]` Not Started  
**Depends on:** `1.5`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Represent consensus, model forecast, and proxy expectations as distinct types.
- Require forecast creation/availability time and source/model provenance.
- Reject expectations that become available at or after the target release in market-surprise mode.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.6): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.7: MarketObservation & Asset Lifecycle Models

**Status:** `[ ]` Not Started  
**Depends on:** `1.6`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Represent market observations plus asset first-tradable/last-tradable coverage metadata.
- Store provider, timezone, adjustment policy, and currency explicitly.
- Prevent coverage before an instrument's tradable lifecycle.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.7): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.8: Return / Execution Contract Models

**Status:** `[ ]` Not Started  
**Depends on:** `1.7`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement typed research-return, execution-price, cash-return, and timing presets.
- Separate signal, decision, execution, and mark timestamps.
- Reject incompatible price/adjustment combinations.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.8): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.9: ResearchSnapshot & ResearchRun Manifests

**Status:** `[ ]` Not Started  
**Depends on:** `1.8`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Create immutable snapshot/run manifests with config hashes, code commit, source snapshots, and protocol id.
- Use stable serialization suitable for reproducibility hashes.
- Ensure a run can be audited without consulting mutable latest configuration files.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.9): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.10: Artifact Registry & Local Storage Layout

**Status:** `[ ]` Not Started  
**Depends on:** `1.9`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement deterministic paths/registry entries for raw snapshots, PIT snapshots, features, model fits, backtests, and reports.
- Do not overwrite immutable run artifacts.
- Provide lookup by run id, snapshot id, and model fit id.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.10): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.11: Synthetic Point-in-Time Fixture Suite

**Status:** `[ ]` Not Started  
**Depends on:** `1.10`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Load bundled vintage, release-stage, ragged-edge, market-price, and state-alignment fixtures.
- Provide fixture helpers usable by unit/integration tests without external APIs.
- Keep fixture semantics intentionally small and deterministic.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.11): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.12: Research Protocol & Hypothesis Registry

**Status:** `[ ]` Not Started  
**Depends on:** `1.11`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Register hypothesis, target, horizon, universe, metrics, sample policy, and exploratory/confirmatory status.
- Require each research run to reference a frozen protocol version.
- Prevent silent mutation of a completed run's protocol.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.12): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 1.13: Project Validation CLI & Repository Health Check

**Status:** `[ ]` Not Started  
**Depends on:** `1.12`

**Purpose**  
Advance Phase 1 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Validate required files, configs, duplicate task ids, unresolved config paths, and secret-prone files.
- Expose one command suitable for local use and CI.
- Return non-zero exit status on blocking repository-integrity failures.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(1.13): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
## Phase 2 — Point-in-Time Data, Release Calendar & Market Data

### Task 2.1: HTTP Client, Retry & Raw Snapshot Layer

**Status:** `[ ]` Not Started  
**Depends on:** `1.13`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Create a provider-neutral HTTP client with timeout, retry/backoff, and deterministic raw-response snapshotting.
- Hash raw payload plus request metadata before normalization.
- Do not retry non-retryable schema/authentication failures indefinitely.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.1): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.2: FRED / ALFRED API Client

**Status:** `[ ]` Not Started  
**Depends on:** `2.1`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement authenticated FRED/ALFRED requests needed by the configured series registry.
- Support pagination/limits and JSON response fixtures.
- Keep API transport separate from macro normalization.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.2): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.3: FRED Series Metadata Normalization

**Status:** `[ ]` Not Started  
**Depends on:** `2.2`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Normalize units, frequency, seasonal adjustment, title, source, and release metadata for configured series.
- Persist source metadata snapshot ids.
- Flag definition changes instead of silently merging incompatible history.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.3): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.4: ALFRED Vintage-Date Retrieval

**Status:** `[ ]` Not Started  
**Depends on:** `2.3`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Retrieve and persist all relevant vintage dates for each PIT-required series.
- Preserve chronological revision history rather than only latest values.
- Test multiple vintages for the same reference observation.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.4): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.5: Initial Release & Revision Observation Retrieval

**Status:** `[ ]` Not Started  
**Depends on:** `2.4`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Use real-time/vintage query semantics to retrieve initial and revised observations distinctly.
- Support initial-release-only retrieval where available.
- Add fixture tests proving today's revised series is not substituted for an initial release.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.5): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.6: Release-Family / Series Mapping Registry

**Status:** `[ ]` Not Started  
**Depends on:** `2.5`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Map configured macro series to official release families and reference-period rules.
- Version mappings separately from source adapters.
- Reject ambiguous mappings instead of guessing exact release time.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.6): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.7: BLS Release Calendar Adapter

**Status:** `[ ]` Not Started  
**Depends on:** `2.6`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Parse BLS scheduled release dates/times with Eastern Time semantics.
- Map supported BLS release families such as CPI and Employment Situation.
- Preserve calendar snapshot/version because schedules can change.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.7): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.8: BEA Release Schedule & Estimate-Stage Adapter

**Status:** `[ ]` Not Started  
**Depends on:** `2.7`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Parse BEA release schedule with exact release times and GDP/PCE release stages.
- Represent advance/second/third estimates separately.
- Map reference periods and release stages without collapsing revisions.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.8): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.9: Federal Reserve FOMC Event Calendar Adapter

**Status:** `[ ]` Not Started  
**Depends on:** `2.8`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Create official FOMC meeting/statement events with statement release timestamps.
- Keep FOMC statement events separate from macro observation releases.
- Do not invent a policy surprise without a valid pre-meeting expectation measure.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.9): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.10: Treasury Nominal & Real Yield-Curve Adapter

**Status:** `[ ]` Not Started  
**Depends on:** `2.9`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Normalize official nominal and real curve observations by maturity.
- Resolve same-day availability conservatively as late-day/end-of-day according to source semantics.
- Prevent morning decisions from consuming that day's late-day curve.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.10): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.11: Availability Resolver & Precision Hierarchy

**Status:** `[ ]` Not Started  
**Depends on:** `2.6, 2.7, 2.8, 2.9, 2.10`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Combine source vintage dates and official release calendars only through documented mappings.
- Emit final availability timestamp, precision, source, and resolver rule.
- Use conservative later availability when exact time cannot be established.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.11): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.12: Point-in-Time As-Of Query Engine

**Status:** `[ ]` Not Started  
**Depends on:** `2.5, 2.11`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement `as_of(timestamp)` returning only values known by that timestamp.
- Select the correct historical vintage/release stage for each reference observation.
- Test pre-release, initial-release, and post-revision queries.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.12): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.13: Immutable PIT Snapshot Builder

**Status:** `[ ]` Not Started  
**Depends on:** `2.12`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Build immutable as-of snapshots with source snapshot ids, resolver version, config hash, and code version.
- Create a stable snapshot hash from canonical inputs.
- Write a quality report for unknown/inferred availability precision.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.13): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 2.14: Daily Market Data Adapter & Trading Calendar

**Status:** `[ ]` Not Started  
**Depends on:** `2.13`

**Purpose**  
Advance Phase 2 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement one documented daily demo market-data provider behind a provider-neutral interface.
- Capture price-field adjustment semantics and instrument coverage/inception.
- Normalize observations to an explicit U.S. trading calendar and cache raw/provider metadata.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(2.14): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
## Phase 3 — Expectations, Ragged-Edge Features & Surprise Engine

### Task 3.1: Macro Series Registry Loader

**Status:** `[ ]` Not Started  
**Depends on:** `2.14`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Load the configured series registry and validate release family, transformations, and staleness thresholds.
- Resolve references to release-map entries.
- Fail if a PIT-required series lacks sufficient timing policy.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.1): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.2: Macro Transformation Registry

**Status:** `[ ]` Not Started  
**Depends on:** `3.1`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement explicit level/difference/YoY/MoM/QoQ-annualized transformation definitions.
- Carry units, seasonal-adjustment assumptions, and feature version into outputs.
- Test transformation arithmetic on synthetic fixtures.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.2): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.3: Inflation Feature Pipeline

**Status:** `[ ]` Not Started  
**Depends on:** `3.2`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Build headline/core CPI and PCE level/momentum features using PIT observations.
- Apply release-aware transformations only after availability.
- Carry age/staleness metadata into each AsOfFeature.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.3): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.4: Labor Feature Pipeline

**Status:** `[ ]` Not Started  
**Depends on:** `3.3`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Build payroll and unemployment features using Employment Situation release timing.
- Preserve revision-aware inputs and family-specific staleness.
- Expose freshness/age for each labor feature.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.4): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.5: Growth / Activity Feature Pipeline

**Status:** `[ ]` Not Started  
**Depends on:** `3.4`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Build GDP and activity features with GDP estimate-stage awareness.
- Do not let a second/third GDP estimate overwrite an earlier historical decision.
- Preserve reference period and release-stage metadata.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.5): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.6: Policy / Rates Feature Pipeline

**Status:** `[ ]` Not Started  
**Depends on:** `3.5`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Build policy-rate and rates-state features with explicit availability timing.
- Include FOMC event markers without fabricating policy surprise.
- Separate same-day late Treasury curve availability from morning macro events.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.6): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.7: Yield-Curve Shape Features

**Status:** `[ ]` Not Started  
**Depends on:** `3.6`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Create level/spread/slope/curvature features from available maturities.
- Handle missing maturities explicitly rather than interpolating silently.
- Preserve observation date and late-day availability metadata.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.7): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.8: Training-Only Yield-Curve PCA

**Status:** `[ ]` Not Started  
**Depends on:** `3.7`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Fit scaler/PCA using only rows available in the training window.
- Freeze loadings/means/scales for subsequent validation/test transformation.
- Add a regression test showing future rows cannot change a historical frozen transform.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.8): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.9: Ragged-Edge AsOfFeatureFrame

**Status:** `[ ]` Not Started  
**Depends on:** `3.3, 3.4, 3.5, 3.6, 3.7`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Create a daily/as-of feature panel that retains value, availability, age, reference age, and stale flag.
- Allow last-known-value representation only while preserving original age.
- Make staleness visible to downstream models and dashboard.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.9): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.10: Expectation Provider Interface

**Status:** `[ ]` Not Started  
**Depends on:** `3.9`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Define one interface for consensus, model forecast, and optional proxy expectations.
- Require pre-release availability and provenance.
- Keep expectation type explicit through all downstream tables.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.10): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.11: Timestamped Consensus CSV Adapter

**Status:** `[ ]` Not Started  
**Depends on:** `3.10`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Import the documented user consensus schema without redistributing proprietary data.
- Map release id/reference period exactly and reject post-release consensus records.
- Produce a validation report for unmatched or ambiguous rows.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.11): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.12: Pre-Release Forecast Baseline

**Status:** `[ ]` Not Started  
**Depends on:** `3.9, 3.10`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement transparent rolling-origin forecast baselines such as naive/AR/regularized linear models.
- Train only on information available before each target release.
- Store forecast creation time, cutoff, model version, and forecast error label.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.12): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.13: Raw Surprise / Forecast-Error Engine

**Status:** `[ ]` Not Started  
**Depends on:** `3.10, 3.11, 3.12`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Compute initial-actual minus valid pre-release expectation.
- Label consensus-derived output `market_surprise` and model-derived output `forecast_error`.
- Return missing rather than fabricate an unavailable expectation.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.13): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 3.14: Point-in-Time Standardization & Composite Surprise Factors

**Status:** `[ ]` Not Started  
**Depends on:** `3.13`

**Purpose**  
Advance Phase 3 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Standardize each release family using scales estimated only from prior releases.
- Define minimum-history and outlier policy explicitly.
- Build transparent inflation/labor/growth composite factors with provenance.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(3.14): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
## Phase 4 — Regime Models, State Alignment & Event Studies

### Task 4.1: Transparent Rule-Based Macro Quadrants

**Status:** `[ ]` Not Started  
**Depends on:** `3.14`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement configurable growth/inflation regime rules using PIT features.
- Keep thresholds training/history-based where statistical thresholds are used.
- Output both canonical label and contributing feature values.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.1): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.2: Regime State / Probability Data Model

**Status:** `[ ]` Not Started  
**Depends on:** `4.1`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Represent model fit id, raw state, canonical state, probability type, fit cutoff, and alignment confidence.
- Distinguish hard labels from probability vectors.
- Make future-informed probability types impossible to pass as live state without an explicit diagnostic flag.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.2): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.3: Gaussian Mixture Regime Baseline

**Status:** `[ ]` Not Started  
**Depends on:** `4.2`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Fit GMM candidates on training history only.
- Store component centroids/covariances, occupancy, fit cutoff, and model config.
- Expose raw component probabilities for later alignment.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.3): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.4: Hidden Markov Model Regime Baseline

**Status:** `[ ]` Not Started  
**Depends on:** `4.3`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Fit HMM candidates on training history only.
- Produce contemporaneous filtered probabilities and separate smoothed diagnostics.
- Store transition matrix, state descriptors, fit cutoff, and random seed.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.4): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.5: Filtered-vs-Smoothed Probability Guard

**Status:** `[ ]` Not Started  
**Depends on:** `4.4`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Block smoothed HMM probabilities from signal/backtest interfaces.
- Permit smoothed probabilities only in explicitly ex-post diagnostics.
- Add a regression test that intentionally attempts leakage and must fail.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.5): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.6: Latent State Canonicalization / Alignment

**Status:** `[ ]` Not Started  
**Depends on:** `4.3, 4.4`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Align newly fitted HMM/GMM raw states to prior canonical state identities using macro descriptors.
- Use a deterministic one-to-one matching method and store mapping distances/confidence.
- Flag ambiguous mappings or changed state counts rather than silently reusing raw ids.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.6): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.7: Regime Probability Uncertainty & Low-Confidence Policy

**Status:** `[ ]` Not Started  
**Depends on:** `4.4, 4.6`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Compute entropy/max-probability or another transparent regime-confidence measure.
- Define how low-confidence regimes affect signals without inventing certainty.
- Expose uncertainty in research outputs and dashboard.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.7): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.8: PCA / Dynamic-Factor Macro-State Baseline

**Status:** `[ ]` Not Started  
**Depends on:** `4.7`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Build a low-dimensional macro-state baseline using training-only transformations.
- Store factor loadings and fit cutoff.
- Keep it independent of future asset returns.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.8): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.9: Regime Model / State-Count Selection Policy

**Status:** `[ ]` Not Started  
**Depends on:** `4.3, 4.4, 4.6`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Evaluate candidate state counts using training/validation criteria such as BIC, stability, occupancy, and persistence.
- Do not select state count using final test-period portfolio Sharpe.
- Register every tested model configuration.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.9): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.10: Regime Persistence, Transition & Alignment Diagnostics

**Status:** `[ ]` Not Started  
**Depends on:** `4.9`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Compute state duration, transition matrix, occupancy, refit stability, and alignment confidence.
- Flag unstable/rare states below configurable thresholds.
- Produce artifacts usable in the final research report.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.10): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.11: Macro Event-to-Market Alignment Engine

**Status:** `[ ]` Not Started  
**Depends on:** `2.14, 2.11`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Map release events to market sessions using event time, timezone, and trading calendar.
- Handle pre-open, market-hours, post-close, weekends, and holidays explicitly.
- Preserve event-time precision and release stage.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.11): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.12: Daily Event-Study Return Windows

**Status:** `[ ]` Not Started  
**Depends on:** `4.11`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Compute declared daily event windows without pretending to observe intraday reactions.
- Separate release-day, next-session, 1D, and 5D conventions.
- Use only asset observations available under the event/return contract.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.12): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.13: Intraday Event-Study Interface

**Status:** `[ ]` Not Started  
**Depends on:** `4.12`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Define the timestamp/frequency contract required for future intraday providers.
- Reject daily provider data passed into intraday windows.
- Keep intraday implementation optional for v1.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.13): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 4.14: Event Clusters, Overlap & Statistical Event Study

**Status:** `[ ]` Not Started  
**Depends on:** `4.11, 4.12`

**Purpose**  
Advance Phase 4 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Detect overlapping/near-simultaneous releases and mark contaminated event clusters.
- Group responses by release family, surprise bucket, and regime with minimum sample checks.
- Produce bootstrap confidence intervals and sample-size diagnostics.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(4.14): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
## Phase 5 — Signals, Returns, Risk Models & Portfolio Construction

### Task 5.1: Cross-Asset Universe & Tradability Resolver

**Status:** `[ ]` Not Started  
**Depends on:** `4.14`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Load configured assets and resolve provider coverage plus first-tradable dates.
- Create an as-of tradable universe for each execution date.
- Never backfill ETF proxies before inception.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.1): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.2: Return Engine & Corporate-Action Semantics

**Status:** `[ ]` Not Started  
**Depends on:** `5.1`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement the configured research-return convention using provider adjustment metadata.
- Validate splits/dividend adjustment consistency and missing sessions.
- Keep return calculation separate from execution-price simulation.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.2): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.3: Cash / Risk-Free Return Engine

**Status:** `[ ]` Not Started  
**Depends on:** `5.2`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement explicit cash policy: zero or configured risk-free proxy.
- Align risk-free observations point-in-time and by trading period.
- Make Sharpe and flat-capital assumptions auditable.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.3): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.4: Ex-Ante Volatility & Covariance Estimation

**Status:** `[ ]` Not Started  
**Depends on:** `5.3`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Estimate volatility/covariance from historical data available at rebalance time only.
- Support a stable shrinkage/regularized covariance baseline.
- Store estimation window and fit timestamp.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.4): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.5: Regime-Based Asset Score

**Status:** `[ ]` Not Started  
**Depends on:** `4.6, 4.7`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Map aligned canonical regime probabilities to transparent per-asset scores.
- Use training/validation data for any learned mapping.
- Expose score decomposition by regime.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.5): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.6: Surprise / Forecast-Error Score with Decay

**Status:** `[ ]` Not Started  
**Depends on:** `3.14`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Map valid surprise/forecast-error factors to asset scores.
- Apply configurable age decay/half-life so old releases lose influence.
- Replace/update signals consistently when newer releases arrive.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.6): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.7: Trend Guardrail Signal

**Status:** `[ ]` Not Started  
**Depends on:** `5.6`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement a simple historical trend/momentum guardrail using only past prices.
- Record lookback and timing semantics.
- Keep trend optional and separately ablatable.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.7): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.8: Combined Transparent Signal Model

**Status:** `[ ]` Not Started  
**Depends on:** `5.5, 5.6, 5.7`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Combine regime, decayed surprise, and optional trend components transparently.
- Select component weights using training/validation only.
- Write per-asset score decomposition artifacts.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.8): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.9: Equal-Weight & Static Allocation Baselines

**Status:** `[ ]` Not Started  
**Depends on:** `5.8`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement simple reproducible benchmark portfolios on the tradable universe.
- Handle asset inception/missing availability explicitly.
- Include cash policy and rebalance schedule.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.9): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.10: Long / Flat Signal Portfolio

**Status:** `[ ]` Not Started  
**Depends on:** `5.9`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Translate positive/negative scores into bounded long/flat allocations.
- Define what unallocated capital does via cash policy.
- Enforce tradability and weight constraints.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.10): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.11: Volatility-Targeted Portfolio

**Status:** `[ ]` Not Started  
**Depends on:** `5.10`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Scale portfolio risk using ex-ante volatility estimates only.
- Apply leverage/weight caps and safe fallback when risk estimates are missing.
- Store target-vol and scaling diagnostics.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.11): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.12: Risk-Parity Portfolio

**Status:** `[ ]` Not Started  
**Depends on:** `5.11`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Compute risk-parity weights from historical/shrunk covariance estimates.
- Enforce tradable universe and numerical stability.
- Report ex-ante risk contributions.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.12): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 5.13: Constrained Mean-Variance & Unified Weight Validator

**Status:** `[ ]` Not Started  
**Depends on:** `5.4, 5.8`

**Purpose**  
Advance Phase 5 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement an optional constrained optimizer using ex-ante inputs only.
- Validate sum, bounds, leverage, turnover, finite weights, and tradability for every portfolio method.
- Provide deterministic fallback when optimization is infeasible.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(5.13): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
## Phase 6 — Walk-Forward Backtesting & Execution Simulation

### Task 6.1: U.S. Trading Calendar & Session Resolver

**Status:** `[ ]` Not Started  
**Depends on:** `5.13`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement market-session resolution for weekends/holidays and required daily execution semantics.
- Keep macro release calendar separate from trading calendar.
- Expose next/previous valid session utilities.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.1): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.2: Chronological Split Utilities

**Status:** `[ ]` Not Started  
**Depends on:** `6.1`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Create explicit train/validation/test date ranges and prevent overlap.
- Support minimum-history requirements.
- Store split definitions in run artifacts.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.2): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.3: Expanding-Window Walk-Forward Engine

**Status:** `[ ]` Not Started  
**Depends on:** `6.2`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Refit configured transforms/models only at allowed refit times using expanding history.
- Produce sequential validation/test predictions without future access.
- Persist fit ids and cutoffs for every window.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.3): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.4: Rolling-Window Walk-Forward Engine

**Status:** `[ ]` Not Started  
**Depends on:** `6.3`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Support fixed-length historical training windows with explicit refit schedule.
- Ensure dropped old data and future data are handled deterministically.
- Record window bounds per fit.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.4): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.5: Blocking Decision-Time Availability Gate

**Status:** `[ ]` Not Started  
**Depends on:** `2.12, 3.9`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Before each decision, verify every required feature/input is available no later than decision time.
- Block the run and identify offending source/feature/timestamps on violation.
- Make the gate non-optional in production backtests.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.5): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.6: Signal-Time / Decision-Time / Execution-Time Policy

**Status:** `[ ]` Not Started  
**Depends on:** `6.1, 6.5`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Represent the full event-to-trade timeline explicitly.
- Resolve daily execution presets through the trading calendar.
- Reject impossible same-bar execution.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.6): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.7: Execution Price & Return-Contract Validator

**Status:** `[ ]` Not Started  
**Depends on:** `5.2, 6.6`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Validate execution fields against provider price semantics and research-return convention.
- Prevent mixing incompatible adjusted/unadjusted fields silently.
- Store the chosen contract in the backtest manifest.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.7): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.8: Transaction Cost & Slippage Model

**Status:** `[ ]` Not Started  
**Depends on:** `6.7`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Apply configurable costs to traded notional/turnover.
- Support base and stressed scenarios.
- Produce gross and net return series separately.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.8): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.9: Turnover & Rebalance Accounting

**Status:** `[ ]` Not Started  
**Depends on:** `6.8`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Compute pre/post-trade weights, notional traded, turnover, and rebalance timestamps.
- Handle asset entry/exit from tradable universe explicitly.
- Feed turnover consistently into transaction costs.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.9): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.10: Portfolio Execution Simulator with Cash

**Status:** `[ ]` Not Started  
**Depends on:** `5.13, 6.6, 6.7, 6.8, 6.9`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Simulate target-to-realized holdings under the execution policy.
- Track cash/uninvested capital and its explicit return.
- Prevent trading unavailable assets or unavailable prices.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.10): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.11: Benchmark & Strategy Ablation Backtests

**Status:** `[ ]` Not Started  
**Depends on:** `6.10`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Run static/equal/vol-target benchmarks plus no-regime, no-surprise, and component ablations.
- Use identical chronology/cost conventions across comparisons.
- Write comparable standardized result artifacts.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.11): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.12: Backtest Run Manifest & Artifact Writer

**Status:** `[ ]` Not Started  
**Depends on:** `6.11`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Persist snapshot ids, fit ids, configs, protocol, search registry, execution contract, costs, and commit hash.
- Make every result table/figure traceable to one run id.
- Prevent silent overwrite of completed run artifacts.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.12): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 6.13: Deterministic Backtest Regression Fixture

**Status:** `[ ]` Not Started  
**Depends on:** `6.11, 6.12`

**Purpose**  
Advance Phase 6 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Freeze a small synthetic/permitted end-to-end backtest with known metrics/hashes.
- CI must fail on unexplained output drift.
- Require deliberate fixture-version change when intended behavior changes.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(6.13): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
## Phase 7 — Evaluation, Robustness & Research Statistics

### Task 7.1: Performance Metrics Suite with Explicit Risk-Free Policy

**Status:** `[ ]` Not Started  
**Depends on:** `6.13`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Compute return, volatility, Sharpe, Sortino, drawdown, Calmar, turnover, and exposure metrics.
- Use the run's explicit cash/risk-free assumption.
- Report gross and net metrics separately.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.1): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.2: Drawdown, Tail Risk & Exposure Analytics

**Status:** `[ ]` Not Started  
**Depends on:** `7.1`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Compute drawdown duration/depth, tail-loss summaries, gross/net exposure, and concentration.
- Use consistent portfolio return series.
- Produce artifacts suitable for dashboard/report.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.2): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.3: Regime-Conditioned Performance Attribution

**Status:** `[ ]` Not Started  
**Depends on:** `4.6, 6.11`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Attribute returns/risk by aligned canonical regime and regime probability confidence.
- Report sample size/time spent per regime.
- Do not use ex-post smoothed regimes for live-strategy attribution unless clearly labeled diagnostic.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.3): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.4: Signal Component Attribution

**Status:** `[ ]` Not Started  
**Depends on:** `7.3`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Decompose portfolio signals and returns into regime, surprise/forecast-error, and trend components where meaningful.
- Keep attribution methodology transparent and reproducible.
- Compare with component-ablation runs.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.4): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.5: Dependence-Aware Event / Strategy Inference

**Status:** `[ ]` Not Started  
**Depends on:** `4.14, 6.11`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Add bootstrap or block-bootstrap confidence intervals for relevant dependent time-series comparisons.
- Support HAC/Newey-West style inference where regression assumptions require it.
- Report sample counts and methodological assumptions.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.5): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.6: Transaction-Cost Sensitivity Analysis

**Status:** `[ ]` Not Started  
**Depends on:** `7.5`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Evaluate zero/base/stressed cost scenarios without retuning the strategy for each test result.
- Report breakeven cost where useful.
- Show turnover alongside net-performance degradation.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.6): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.7: Subperiod / Crisis Robustness Analysis

**Status:** `[ ]` Not Started  
**Depends on:** `7.6`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Evaluate pre-specified subperiods and crisis/non-crisis partitions.
- Keep partitions fixed before reading test-period performance where possible.
- Report whether results are concentrated in one episode.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.7): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.8: Asset-Universe Ablation Analysis

**Status:** `[ ]` Not Started  
**Depends on:** `7.7`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Remove asset groups one at a time and rerun comparable tests.
- Respect each asset's actual tradable lifecycle.
- Report dependence on a single proxy/instrument.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.8): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.9: Alternative Regime-Model Comparison

**Status:** `[ ]` Not Started  
**Depends on:** `4.9, 6.11`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Compare rule-based, GMM, HMM, and factor-state approaches on identical splits.
- Include state stability/alignment diagnostics, not only portfolio returns.
- Keep model selection separate from final test evaluation.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.9): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.10: Hyperparameter / Variant Search Audit Trail

**Status:** `[ ]` Not Started  
**Depends on:** `7.9`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Register every tested model, horizon, signal weight, decay, universe, and portfolio setting.
- Store selection metric and train/validation result.
- Prevent unregistered ad-hoc test-set tuning.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.10): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.11: Selection-Bias / Deflated-Performance Diagnostics

**Status:** `[ ]` Not Started  
**Depends on:** `7.10`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Generate a plain-language disclosure of search breadth and selection bias.
- Optionally compute probabilistic/deflated Sharpe-style diagnostics when assumptions are documented.
- Never present the best observed Sharpe without search context.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.11): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 7.12: Reproducible Research Report Builder

**Status:** `[ ]` Not Started  
**Depends on:** `7.11`

**Purpose**  
Advance Phase 7 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Generate tables/figures for data integrity, regimes, event studies, backtests, robustness, and limitations.
- Include null/negative results and PIT methodology.
- Embed run ids/config hashes/source provenance in the report metadata.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(7.12): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
## Phase 8 — Dashboard, CLI, CI/CD & Portfolio Release

### Task 8.1: Streamlit App Foundation & Run Selector

**Status:** `[ ]` Not Started  
**Depends on:** `7.12`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Create a read-only dashboard shell that loads immutable run artifacts.
- Allow selecting a completed run/snapshot without recomputing research silently.
- Display run metadata and integrity status.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.1): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.2: Macro Snapshot & Ragged-Edge Freshness Dashboard

**Status:** `[ ]` Not Started  
**Depends on:** `8.1`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Show current/historical macro factors plus feature age, stale flags, and availability precision.
- Allow selecting an as-of date.
- Do not substitute today's revised values for historical snapshot inputs.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.2): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.3: Release / Expectation / Surprise Dashboard

**Status:** `[ ]` Not Started  
**Depends on:** `8.2`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Display release timestamp/stage, initial actual, expectation type/value, surprise or forecast error, and provenance.
- Clearly distinguish market surprise from model forecast error.
- Flag missing/unmatched expectations.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.3): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.4: Yield Curve & Macro Transformation Dashboard

**Status:** `[ ]` Not Started  
**Depends on:** `8.3`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Show nominal/real curve, spreads, transformation definitions, and observation availability.
- Indicate when same-day Treasury data are late-day only.
- Expose feature version and staleness.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.4): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.5: Regime Timeline, State Alignment & Transition Dashboard

**Status:** `[ ]` Not Started  
**Depends on:** `8.4`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Show aligned canonical regimes, filtered probabilities, transition matrix, and alignment confidence.
- Expose raw-state-to-canonical mapping per refit.
- Keep smoothed probabilities visually labeled ex-post only.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.5): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.6: Cross-Asset Event Study Dashboard

**Status:** `[ ]` Not Started  
**Depends on:** `8.5`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Provide release family, surprise bucket, regime, and event-window filters.
- Show sample size, overlap flags, mean/median response, and confidence intervals.
- Block intraday views when underlying run contains only daily data.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.6): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.7: Portfolio / Backtest / Drawdown Dashboard

**Status:** `[ ]` Not Started  
**Depends on:** `8.6`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Show asset scores, target weights, realized weights, costs, turnover, equity curve, drawdown, and benchmarks.
- Display gross and net results together.
- Expose tradable-universe changes over time.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.7): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.8: Historical Decision Audit Trail

**Status:** `[ ]` Not Started  
**Depends on:** `6.12, 7.12`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- For any rebalance, display exact source snapshots, vintages, availability precision, feature ages, expectations, aligned regime, signals, weights, and execution policy.
- Use stored run artifacts only.
- Make the decision reproducible from run id and timestamp.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.8): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.9: Typer CLI & One-Command Practical Demo

**Status:** `[ ]` Not Started  
**Depends on:** `8.1, 8.8`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Implement CLI commands for data build, features, regimes, backtest, report, and validation.
- Provide a documented demo command sequence using free-research mode.
- Fail clearly when optional API credentials are missing.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.9): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.10: GitHub Actions CI & Clean-Clone Reproduction

**Status:** `[ ]` Not Started  
**Depends on:** `6.13, 8.9`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Run repository validation, tests, PIT regression fixtures, and deterministic backtest fixture in CI.
- Add a clean-clone job that requires no external API keys.
- Fail on chronology leakage or fixture drift.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.10): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---
### Task 8.11: Secrets, Data Licensing & Portfolio Release Checklist

**Status:** `[ ]` Not Started  
**Depends on:** `8.10`

**Purpose**  
Advance Phase 8 while preserving point-in-time integrity, research
reproducibility, and practical usability.

**Task-Specific Implementation Contract**
- Verify no API keys, proprietary consensus data, restricted raw data, or unlicensed assets are committed.
- Run clean setup/demo/documentation checks.
- Prepare final README screenshots/results checklist and tag/release instructions without rewriting history.

**Required Verification**
- Run tests/validation directly relevant to this task.
- Run chronology/PIT checks whenever the task touches data, availability, features, models, signals, portfolios, or backtests.
- Run `git diff --check`.
- Confirm no unrelated files, secrets, or restricted raw data are staged.

**Definition of Done**
- [ ] Task-specific implementation exists.
- [ ] Relevant automated validation passes.
- [ ] PIT / chronology invariants pass where applicable.
- [ ] Research provenance is preserved.
- [ ] Documentation and task status are synchronized.
- [ ] A dedicated `task(8.11): ...` commit exists.
- [ ] Commit is pushed and upstream is verified when `origin` is configured.
- [ ] Claude stops before the next task.

---

## Progress Summary

| Phase | Tasks | Completed |
|---|---:|---:|
| 1 — Foundation, Reproducibility & Research Protocol | 13 | 0 |
| 2 — Point-in-Time Data, Release Calendar & Market Data | 14 | 0 |
| 3 — Expectations, Ragged-Edge Features & Surprise Engine | 14 | 0 |
| 4 — Regime Models, State Alignment & Event Studies | 14 | 0 |
| 5 — Signals, Returns, Risk Models & Portfolio Construction | 13 | 0 |
| 6 — Walk-Forward Backtesting & Execution Simulation | 13 | 0 |
| 7 — Evaluation, Robustness & Research Statistics | 12 | 0 |
| 8 — Dashboard, CLI, CI/CD & Portfolio Release | 11 | 0 |
| **Total** | **104** | **0** |
