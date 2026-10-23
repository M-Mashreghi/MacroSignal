
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
