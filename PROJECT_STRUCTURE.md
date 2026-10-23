
# MacroSignal — Project Structure

```text
MacroSignal/
│
├── CLAUDE.md
├── README.md
├── PROJECT_STRUCTURE.md
├── pyproject.toml
├── Makefile
├── .env.example
├── .gitignore
│
├── .claude/
│   └── rules/
│       ├── architecture.md
│       ├── point-in-time.md
│       ├── availability.md
│       ├── macro-data.md
│       ├── ragged-edge.md
│       ├── expectations.md
│       ├── regime-integrity.md
│       ├── event-study.md
│       ├── returns-execution.md
│       ├── backtesting.md
│       ├── statistics.md
│       ├── testing.md
│       ├── git-workflow.md
│       └── documentation.md
│
├── docs/
│   ├── PRACTICAL_MVP.md
│   ├── ARCHITECTURE.md
│   ├── RESEARCH_QUESTIONS.md
│   ├── DATA_CONTRACT.md
│   ├── DATA_SOURCES.md
│   ├── DATA_QUALITY_POLICY.md
│   ├── AVAILABILITY_RESOLUTION.md
│   ├── POINT_IN_TIME_POLICY.md
│   ├── RELEASE_CALENDAR_SPEC.md
│   ├── RAGGED_EDGE_POLICY.md
│   ├── EXPECTATIONS_AND_SURPRISES.md
│   ├── MACRO_FEATURES.md
│   ├── MODEL_SELECTION_POLICY.md
│   ├── REGIME_MODELING.md
│   ├── REGIME_STATE_ALIGNMENT.md
│   ├── EVENT_STUDY.md
│   ├── SIGNAL_DESIGN.md
│   ├── RETURN_AND_EXECUTION_CONTRACT.md
│   ├── PORTFOLIO_POLICY.md
│   ├── BACKTEST_POLICY.md
│   ├── PERFORMANCE_STATISTICS.md
│   ├── EVALUATION_PROTOCOL.md
│   ├── VALIDATION_MATRIX.md
│   ├── DASHBOARD_SPEC.md
│   ├── DEMO_PLAN.md
│   ├── DATA_LICENSE_POLICY.md
│   ├── REFERENCES.md
│   ├── ROADMAP.md
│   ├── PHASES.md
│   ├── TASK_DEPENDENCIES.md
│   ├── PROJECT_PHASES_AND_TASKS.md
│   ├── TASKS.md
│   ├── DIAGRAMS.md
│   ├── DEPLOYMENT.md
│   ├── RUNBOOK.md
│   ├── FINAL_AUDIT.md
│   ├── GIT_WORKFLOW.md
│   └── REVIEW_NOTES_v3.md
│
├── configs/
│   ├── series/
│   │   ├── us_macro_v1.yaml
│   │   └── release_map_v1.yaml
│   ├── assets/
│   │   └── cross_asset_v1.yaml
│   ├── regimes/
│   │   └── regimes_v1.yaml
│   ├── signals/
│   │   └── signals_v1.yaml
│   └── research/
│       ├── demo_daily.yaml
│       ├── event_study.yaml
│       └── walk_forward.yaml
│
├── examples/
│   ├── consensus_template.csv
│   ├── release_calendar_fixture.csv
│   ├── release_stage_fixture.csv
│   ├── vintage_fixture.csv
│   ├── ragged_edge_fixture.csv
│   ├── market_price_fixture.csv
│   ├── state_alignment_fixture.csv
│   └── README.md
│
├── src/macrosignal/
│   ├── config/
│   ├── domain/
│   ├── data/
│   │   ├── fred_alfred/
│   │   ├── bls/
│   │   ├── bea/
│   │   ├── federal_reserve/
│   │   ├── treasury/
│   │   ├── expectations/
│   │   └── market/
│   ├── calendar/
│   ├── availability/
│   ├── pit/
│   ├── features/
│   ├── surprises/
│   ├── regimes/
│   ├── event_study/
│   ├── signals/
│   ├── portfolio/
│   ├── backtest/
│   ├── evaluation/
│   ├── reporting/
│   └── dashboard/
│
├── data/
│   ├── raw/
│   ├── snapshots/
│   ├── processed/
│   └── cache/
│
├── reports/
│   ├── tables/
│   ├── figures/
│   └── runs/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── pit/
│   └── regression/
│
├── scripts/
│   ├── bootstrap.sh
│   └── validate_project.py
│
└── .github/
    └── workflows/
        └── ci.yml
```
