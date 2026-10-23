# Task Dependencies

The task plan is intentionally sequential, but several tasks have explicit
cross-dependencies.

| Task | Depends on |
|---|---|
| 1.1 — Complete Python Package Scaffold & Development Tooling | None |
| 1.2 — GitHub Remote & Per-Task Commit Workflow Baseline | 1.1 |
| 1.3 — Typed Configuration Loader & Environment Separation | 1.2 |
| 1.4 — MacroObservation Domain Model | 1.3 |
| 1.5 — AvailabilityStamp & ReleaseEvent Domain Models | 1.4 |
| 1.6 — ExpectationObservation & Forecast Provenance Models | 1.5 |
| 1.7 — MarketObservation & Asset Lifecycle Models | 1.6 |
| 1.8 — Return / Execution Contract Models | 1.7 |
| 1.9 — ResearchSnapshot & ResearchRun Manifests | 1.8 |
| 1.10 — Artifact Registry & Local Storage Layout | 1.9 |
| 1.11 — Synthetic Point-in-Time Fixture Suite | 1.10 |
| 1.12 — Research Protocol & Hypothesis Registry | 1.11 |
| 1.13 — Project Validation CLI & Repository Health Check | 1.12 |
| 2.1 — HTTP Client, Retry & Raw Snapshot Layer | 1.13 |
| 2.2 — FRED / ALFRED API Client | 2.1 |
| 2.3 — FRED Series Metadata Normalization | 2.2 |
| 2.4 — ALFRED Vintage-Date Retrieval | 2.3 |
| 2.5 — Initial Release & Revision Observation Retrieval | 2.4 |
| 2.6 — Release-Family / Series Mapping Registry | 2.5 |
| 2.7 — BLS Release Calendar Adapter | 2.6 |
| 2.8 — BEA Release Schedule & Estimate-Stage Adapter | 2.7 |
| 2.9 — Federal Reserve FOMC Event Calendar Adapter | 2.8 |
| 2.10 — Treasury Nominal & Real Yield-Curve Adapter | 2.9 |
| 2.11 — Availability Resolver & Precision Hierarchy | 2.6, 2.7, 2.8, 2.9, 2.10 |
| 2.12 — Point-in-Time As-Of Query Engine | 2.5, 2.11 |
| 2.13 — Immutable PIT Snapshot Builder | 2.12 |
| 2.14 — Daily Market Data Adapter & Trading Calendar | 2.13 |
| 3.1 — Macro Series Registry Loader | 2.14 |
| 3.2 — Macro Transformation Registry | 3.1 |
| 3.3 — Inflation Feature Pipeline | 3.2 |
| 3.4 — Labor Feature Pipeline | 3.3 |
| 3.5 — Growth / Activity Feature Pipeline | 3.4 |
| 3.6 — Policy / Rates Feature Pipeline | 3.5 |
| 3.7 — Yield-Curve Shape Features | 3.6 |
| 3.8 — Training-Only Yield-Curve PCA | 3.7 |
| 3.9 — Ragged-Edge AsOfFeatureFrame | 3.3, 3.4, 3.5, 3.6, 3.7 |
| 3.10 — Expectation Provider Interface | 3.9 |
| 3.11 — Timestamped Consensus CSV Adapter | 3.10 |
| 3.12 — Pre-Release Forecast Baseline | 3.9, 3.10 |
| 3.13 — Raw Surprise / Forecast-Error Engine | 3.10, 3.11, 3.12 |
| 3.14 — Point-in-Time Standardization & Composite Surprise Factors | 3.13 |
| 4.1 — Transparent Rule-Based Macro Quadrants | 3.14 |
| 4.2 — Regime State / Probability Data Model | 4.1 |
| 4.3 — Gaussian Mixture Regime Baseline | 4.2 |
| 4.4 — Hidden Markov Model Regime Baseline | 4.3 |
| 4.5 — Filtered-vs-Smoothed Probability Guard | 4.4 |
| 4.6 — Latent State Canonicalization / Alignment | 4.3, 4.4 |
| 4.7 — Regime Probability Uncertainty & Low-Confidence Policy | 4.4, 4.6 |
| 4.8 — PCA / Dynamic-Factor Macro-State Baseline | 4.7 |
| 4.9 — Regime Model / State-Count Selection Policy | 4.3, 4.4, 4.6 |
| 4.10 — Regime Persistence, Transition & Alignment Diagnostics | 4.9 |
| 4.11 — Macro Event-to-Market Alignment Engine | 2.14, 2.11 |
| 4.12 — Daily Event-Study Return Windows | 4.11 |
| 4.13 — Intraday Event-Study Interface | 4.12 |
| 4.14 — Event Clusters, Overlap & Statistical Event Study | 4.11, 4.12 |
| 5.1 — Cross-Asset Universe & Tradability Resolver | 4.14 |
| 5.2 — Return Engine & Corporate-Action Semantics | 5.1 |
| 5.3 — Cash / Risk-Free Return Engine | 5.2 |
| 5.4 — Ex-Ante Volatility & Covariance Estimation | 5.3 |
| 5.5 — Regime-Based Asset Score | 4.6, 4.7 |
| 5.6 — Surprise / Forecast-Error Score with Decay | 3.14 |
| 5.7 — Trend Guardrail Signal | 5.6 |
| 5.8 — Combined Transparent Signal Model | 5.5, 5.6, 5.7 |
| 5.9 — Equal-Weight & Static Allocation Baselines | 5.8 |
| 5.10 — Long / Flat Signal Portfolio | 5.9 |
| 5.11 — Volatility-Targeted Portfolio | 5.10 |
| 5.12 — Risk-Parity Portfolio | 5.11 |
| 5.13 — Constrained Mean-Variance & Unified Weight Validator | 5.4, 5.8 |
| 6.1 — U.S. Trading Calendar & Session Resolver | 5.13 |
| 6.2 — Chronological Split Utilities | 6.1 |
| 6.3 — Expanding-Window Walk-Forward Engine | 6.2 |
| 6.4 — Rolling-Window Walk-Forward Engine | 6.3 |
| 6.5 — Blocking Decision-Time Availability Gate | 2.12, 3.9 |
| 6.6 — Signal-Time / Decision-Time / Execution-Time Policy | 6.1, 6.5 |
| 6.7 — Execution Price & Return-Contract Validator | 5.2, 6.6 |
| 6.8 — Transaction Cost & Slippage Model | 6.7 |
| 6.9 — Turnover & Rebalance Accounting | 6.8 |
| 6.10 — Portfolio Execution Simulator with Cash | 5.13, 6.6, 6.7, 6.8, 6.9 |
| 6.11 — Benchmark & Strategy Ablation Backtests | 6.10 |
| 6.12 — Backtest Run Manifest & Artifact Writer | 6.11 |
| 6.13 — Deterministic Backtest Regression Fixture | 6.11, 6.12 |
| 7.1 — Performance Metrics Suite with Explicit Risk-Free Policy | 6.13 |
| 7.2 — Drawdown, Tail Risk & Exposure Analytics | 7.1 |
| 7.3 — Regime-Conditioned Performance Attribution | 4.6, 6.11 |
| 7.4 — Signal Component Attribution | 7.3 |
| 7.5 — Dependence-Aware Event / Strategy Inference | 4.14, 6.11 |
| 7.6 — Transaction-Cost Sensitivity Analysis | 7.5 |
| 7.7 — Subperiod / Crisis Robustness Analysis | 7.6 |
| 7.8 — Asset-Universe Ablation Analysis | 7.7 |
| 7.9 — Alternative Regime-Model Comparison | 4.9, 6.11 |
| 7.10 — Hyperparameter / Variant Search Audit Trail | 7.9 |
| 7.11 — Selection-Bias / Deflated-Performance Diagnostics | 7.10 |
| 7.12 — Reproducible Research Report Builder | 7.11 |
| 8.1 — Streamlit App Foundation & Run Selector | 7.12 |
| 8.2 — Macro Snapshot & Ragged-Edge Freshness Dashboard | 8.1 |
| 8.3 — Release / Expectation / Surprise Dashboard | 8.2 |
| 8.4 — Yield Curve & Macro Transformation Dashboard | 8.3 |
| 8.5 — Regime Timeline, State Alignment & Transition Dashboard | 8.4 |
| 8.6 — Cross-Asset Event Study Dashboard | 8.5 |
| 8.7 — Portfolio / Backtest / Drawdown Dashboard | 8.6 |
| 8.8 — Historical Decision Audit Trail | 6.12, 7.12 |
| 8.9 — Typer CLI & One-Command Practical Demo | 8.1, 8.8 |
| 8.10 — GitHub Actions CI & Clean-Clone Reproduction | 6.13, 8.9 |
| 8.11 — Secrets, Data Licensing & Portfolio Release Checklist | 8.10 |
