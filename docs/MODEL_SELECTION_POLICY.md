
# Model Selection Policy

## Regime Model Complexity

Select:
- number of GMM components,
- HMM state count,
- covariance structure,
- regularization,

using training/validation only.

Useful criteria may include:
- likelihood-based criteria,
- stability,
- minimum state occupancy,
- persistence,
- interpretability.

Do not select the number of states using final test-period portfolio Sharpe.

## Forecast Models

Expectation / forecast baselines should begin with transparent models:
- naive / last value,
- autoregressive,
- regularized linear model.

Complexity must earn its place out of sample.

## Hyperparameters

Every trial is registered.

Final report includes:
- candidate set,
- selection metric,
- selected configuration,
- test period held out.
