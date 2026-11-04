"""Gaussian-mixture regime baseline fitted on training history only.

``fit_gmm`` standardizes the training-window rows of an
:class:`AsOfFeatureFrame` with a frozen scaler and fits a full-covariance
``sklearn.mixture.GaussianMixture`` with a fixed seed for each candidate
component count.  Each :class:`GmmFit` stores component weights, centroids
(standardized and in original feature units), covariances, training occupancy,
BIC / log-likelihood, the fit cutoff, training window and the model config.

``GmmFit.posterior_state`` returns the raw component probabilities of a later
row as a :class:`~macrosignal.domain.regime.RegimeObservation` of type
``mixture_posterior`` - *unaligned*: raw component ids carry no meaning until
Task 4.6 maps them to canonical identities.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sklearn.mixture import GaussianMixture  # type: ignore[import-untyped]

from macrosignal.domain.manifest import stable_hash
from macrosignal.domain.regime import ProbabilityType, RegimeObservation, StateKind
from macrosignal.features.frame import AsOfFeatureFrame
from macrosignal.regimes.training import FrozenScaler, TrainingDataError, training_matrix

GMM_VERSION = "gmm-1"


class GmmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    features: tuple[str, ...] = Field(min_length=1)
    n_components: int = Field(ge=1)
    seed: int = 0
    n_init: int = Field(default=5, ge=1)
    covariance_type: str = "full"
    reg_covar: float = Field(default=1e-6, gt=0)
    min_rows_per_component: int = Field(default=5, ge=1)


class GmmFit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_id: str
    config: GmmConfig
    fit_cutoff: AwareDatetime
    train_start: AwareDatetime
    train_end: AwareDatetime
    n_train: int
    n_excluded_incomplete: int
    scaler: FrozenScaler
    weights: tuple[float, ...]
    means_std: tuple[tuple[float, ...], ...]
    means_original: tuple[tuple[float, ...], ...]
    covariances: tuple[tuple[tuple[float, ...], ...], ...]
    occupancy: tuple[float, ...]
    bic: float
    log_likelihood: float
    converged: bool
    version: str = GMM_VERSION

    @property
    def params_hash(self) -> str:
        return stable_hash(self.model_dump(mode="python", exclude={"fit_id"}))

    def _model(self) -> GaussianMixture:
        k = self.config.n_components
        gm = GaussianMixture(n_components=k, covariance_type="full")
        gm.weights_ = np.array(self.weights)
        gm.means_ = np.array(self.means_std)
        cov = np.array(self.covariances)
        gm.covariances_ = cov
        gm.precisions_cholesky_ = np.array([np.linalg.cholesky(np.linalg.inv(c)) for c in cov])
        return gm

    def raw_probabilities(self, row: Mapping[str, float]) -> dict[int, float]:
        missing = [f for f in self.config.features if f not in row]
        if missing:
            raise TrainingDataError(f"missing features {missing}; GMM does not impute")
        x = self.scaler.transform(np.array([[row[f] for f in self.config.features]]))
        probs = self._model().predict_proba(x)[0]
        probs = probs / probs.sum()
        return {i: float(p) for i, p in enumerate(probs)}

    def posterior_state(self, as_of: datetime, row: Mapping[str, float]) -> RegimeObservation:
        return RegimeObservation(
            as_of=as_of,
            fit_id=self.fit_id,
            model_version=self.version,
            fit_cutoff=self.fit_cutoff,
            probability_type=ProbabilityType.MIXTURE_POSTERIOR,
            kind=StateKind.PROBABILITY_VECTOR,
            raw_probabilities=self.raw_probabilities(row),
        )


def fit_gmm(frame: AsOfFeatureFrame, config: GmmConfig, cutoff: datetime, fit_id: str) -> GmmFit:
    k = config.n_components
    times, x, excluded = training_matrix(
        frame, config.features, cutoff, min_rows=max(k * config.min_rows_per_component, 2)
    )
    scaler = FrozenScaler.fit(config.features, x)
    z = scaler.transform(x)
    gm = GaussianMixture(
        n_components=k,
        covariance_type=config.covariance_type,
        random_state=config.seed,
        n_init=config.n_init,
        reg_covar=config.reg_covar,
    ).fit(z)
    labels = gm.predict(z)
    occupancy = np.bincount(labels, minlength=k) / len(labels)
    covs = np.asarray(gm.covariances_)
    means_orig = gm.means_ * np.array(scaler.scales) + np.array(scaler.means)
    return GmmFit(
        fit_id=fit_id,
        config=config,
        fit_cutoff=cutoff,
        train_start=times[0],
        train_end=times[-1],
        n_train=len(times),
        n_excluded_incomplete=excluded,
        scaler=scaler,
        weights=tuple(map(float, gm.weights_)),
        means_std=tuple(tuple(map(float, m)) for m in gm.means_),
        means_original=tuple(tuple(map(float, m)) for m in means_orig),
        covariances=tuple(tuple(tuple(map(float, r)) for r in c) for c in covs),
        occupancy=tuple(map(float, occupancy)),
        bic=float(gm.bic(z)),
        log_likelihood=float(gm.score(z) * len(z)),
        converged=bool(gm.converged_),
    )


def fit_gmm_candidates(
    frame: AsOfFeatureFrame,
    features: Sequence[str],
    candidate_states: Sequence[int],
    cutoff: datetime,
    *,
    seed: int = 0,
    fit_id_prefix: str = "gmm",
) -> list[GmmFit]:
    return [
        fit_gmm(
            frame,
            GmmConfig(features=tuple(features), n_components=k, seed=seed),
            cutoff,
            f"{fit_id_prefix}_k{k}_{cutoff:%Y%m%d}",
        )
        for k in candidate_states
    ]
