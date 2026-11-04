
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
