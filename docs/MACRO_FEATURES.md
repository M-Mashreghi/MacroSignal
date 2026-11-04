
# Macro Feature Specification

## Transformation Registry

Every feature declares:
- input series,
- level / difference / percent change,
- YoY / MoM / QoQ convention,
- annualization,
- seasonal adjustment,
- lag,
- winsorization if any,
- standardization policy,
- staleness threshold.

## Inflation
- headline CPI YoY / MoM
- core CPI YoY / MoM
- PCE / core PCE
- inflation momentum
- inflation surprise / forecast-error factor

## Labor
- payroll change / momentum
- unemployment level / change
- ECI / wage-related feature where practical
- labor surprise / forecast-error factor

## Growth
- real GDP growth with estimate-stage awareness
- industrial production / activity
- consumption / income
- growth surprise / forecast-error factor

## Policy / Rates
- policy-rate state
- FOMC event marker
- nominal curve
- real curve
- curve slope / curvature

## Yield Curve
Core:
- 2Y
- 5Y
- 10Y
- 30Y
- 10Y-2Y
- 10Y-3M when supported

Optional PCA:
- level
- slope
- curvature

PCA is training-only.

## Ragged Edge

Every transformed feature retains:
- last source availability,
- age,
- stale flag.

The daily feature panel does not erase publication lags.

## Series Registry Loader (Task 3.1)

`configs/series/us_macro_v2.yaml` (registry v3; v1 kept unchanged) adds an
explicit `timing_policy` per series: `release_calendar` (availability may be
resolved to an exact time through the release-family mapping) or
`vintage_date_conservative` (no official family; ALFRED vintage dates at
conservative end of day). Research configs now reference it.

`macrosignal.features.series_registry.load_series_catalog(registry, release_map)`
resolves every series to its `SeriesReleaseMapping` and fails with all problems
listed (`SeriesRegistryError`) when: a transformation is unknown
(`level`, `level_diff`, `mom_diff`, `mom_pct`, `yoy_pct`, `qoq_annualized`,
`qoq_pct`); a frequency-specific transformation does not match the family's
reference frequency; `stale_after_days` is shorter than one reference period;
or a PIT-required series lacks a timing policy, declares one that contradicts
its release family, or uses a provider without vintages.

## Transformation Registry (Task 3.2)

`macrosignal.features.transformations.TRANSFORMATIONS` defines, for each name,
its formula, lag, accepted frequencies and output units:

| name | formula | frequencies | units |
|---|---|---|---|
| `level` | x_t | all | input units |
| `level_diff` | x_t - x_{t-1} | all | input units |
| `mom_diff` | x_t - x_{t-1} | monthly | input units |
| `mom_pct` | 100(x_t/x_{t-1} - 1) | monthly | `percent_mom` |
| `qoq_pct` | 100(x_t/x_{t-1} - 1) | quarterly | `percent_qoq` |
| `qoq_annualized` | 100((x_t/x_{t-1})^4 - 1) | quarterly | `percent_annualized` |
| `yoy_pct` | 100(x_t/x_{t-k} - 1), k = 12 / 4 | monthly, quarterly | `percent_yoy` |

`transform(observations, name, series_key=...)` works on one series' as-of
view (one vintage per reference period). Outputs (`TransformedValue`) carry
feature name/version, units, seasonal adjustment, frequency, release stage,
input snapshot ids, `available_at = max(input availability)` and the worst
input precision. Missing lag periods and non-positive bases produce no value
(no interpolation), and mixed units / frequency / seasonal adjustment, mixed
series or duplicate vintages raise `TransformationError`.

## Labor Pipeline (Task 3.4)

`macrosignal.features.labor.build_labor_features(store, catalog, t, events)`
requires labor series to map to `EMPLOYMENT_SITUATION` with `release_calendar`
timing and builds payroll / unemployment level and `mom_diff` features from the
revision-aware as-of view (a revised earlier month replaces the old vintage only
from its own release onwards). Thresholds come from each series'
`stale_after_days`. Besides each feature's age, the result reports the latest
Employment Situation release known at `t` (actual releases only) and
`overdue_features`: features not updated since that release, or missing, so an
absent update is visible rather than silently carried.
