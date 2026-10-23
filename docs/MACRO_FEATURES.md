
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
