
# Runbook

## Availability Precision Conflict
- inspect raw vintage/release timing,
- verify release-family mapping,
- prefer conservative later time,
- do not promote date-only evidence to an exact timestamp without source support.

## Missing Consensus
- market surprise stays missing,
- optionally run forecast-error mode,
- never synthesize consensus from actuals.

## Regime State Flip After Refit
- inspect canonical alignment artifact,
- check centroid distances/alignment confidence,
- stop strategy use if mapping is ambiguous.

## Asset Missing Before Inception
- remove from tradable universe,
- do not proxy/backfill silently,
- allow portfolio to re-normalize according to policy.

## Treasury Same-Day Timing
- treat daily official curve as late-day/end-of-day,
- do not use it in same-morning decisions.

## Suspiciously Strong Strategy
Check:
1. vintage leakage,
2. exact-vs-date-only availability,
3. stale-feature treatment,
4. smoothed HMM leakage,
5. raw state-id switching,
6. asset inception leakage,
7. return-adjustment mismatch,
8. impossible execution price,
9. missing costs,
10. search/selection bias.
