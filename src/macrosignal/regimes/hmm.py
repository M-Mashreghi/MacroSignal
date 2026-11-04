"""Gaussian hidden Markov model regime baseline (numpy, training history only).

A transparent full-covariance Gaussian HMM fitted by Baum-Welch (EM with scaled
forward-backward) on the standardized training-window rows of an
:class:`AsOfFeatureFrame`.  Initialization is deterministic: a seeded Gaussian
mixture provides the starting means/covariances.  :class:`HmmFit` stores the
transition matrix, initial distribution, state means (standardized and
original units), covariances, training occupancy, log-likelihood, BIC, fit
cutoff, seed and iteration count.

Probabilities:

* :meth:`HmmFit.filtered_states` - P(s_t | x_1..x_t) computed by a forward pass
  over rows up to each decision time: **contemporaneous**, usable live
  (``probability_type = filtered``, unaligned raw state ids);
* :meth:`HmmFit.smoothed_diagnostics` - P(s_t | x_1..x_T) via forward-backward
  over the whole sample: **future-informed**, always emitted with
  ``diagnostic=True`` so it cannot become live state.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sklearn.mixture import GaussianMixture  # type: ignore[import-untyped]

from macrosignal.domain.manifest import stable_hash
from macrosignal.domain.regime import ProbabilityType, RegimeObservation, StateKind
from macrosignal.features.frame import AsOfFeatureFrame
from macrosignal.regimes.training import FrozenScaler, frame_rows, training_matrix

HMM_VERSION = "hmm-1"


class HmmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    features: tuple[str, ...] = Field(min_length=1)
    n_states: int = Field(ge=2)
    seed: int = 0
    max_iter: int = Field(default=200, ge=1)
    tol: float = Field(default=1e-6, gt=0)
    reg_covar: float = Field(default=1e-4, gt=0)
    min_rows_per_state: int = Field(default=5, ge=1)


def _log_gauss(z: np.ndarray, means: np.ndarray, covs: np.ndarray) -> np.ndarray:
    """log N(z_t | mu_k, Sigma_k) for all t, k -> (T, K)."""
    t_len, d = z.shape
    out = np.empty((t_len, len(means)))
    for k, (mu, cov) in enumerate(zip(means, covs, strict=True)):
        chol = np.linalg.cholesky(cov)
        diff = np.linalg.solve(chol, (z - mu).T)
        maha = np.sum(diff**2, axis=0)
        logdet = 2 * np.sum(np.log(np.diag(chol)))
        out[:, k] = -0.5 * (d * np.log(2 * np.pi) + logdet + maha)
    return out


def _forward(
    logb: np.ndarray, start: np.ndarray, trans: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Scaled forward pass: filtered alphas (T, K) and log scaling constants (T,)."""
    t_len, k = logb.shape
    alpha = np.empty((t_len, k))
    log_c = np.empty(t_len)
    for t in range(t_len):
        m = logb[t].max()
        b = np.exp(logb[t] - m)
        a = start * b if t == 0 else (alpha[t - 1] @ trans) * b
        s = a.sum()
        alpha[t] = a / s
        log_c[t] = np.log(s) + m
    return alpha, log_c


def _backward(logb: np.ndarray, trans: np.ndarray, log_c: np.ndarray) -> np.ndarray:
    t_len, k = logb.shape
    beta = np.ones((t_len, k))
    for t in range(t_len - 2, -1, -1):
        m = logb[t + 1].max()
        b = np.exp(logb[t + 1] - m)
        beta[t] = trans @ (b * beta[t + 1]) / np.exp(log_c[t + 1] - m)
    return beta


class HmmFit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_id: str
    config: HmmConfig
    fit_cutoff: AwareDatetime
    train_start: AwareDatetime
    train_end: AwareDatetime
    n_train: int
    n_excluded_incomplete: int
    scaler: FrozenScaler
    start_prob: tuple[float, ...]
    transition: tuple[tuple[float, ...], ...]
    means_std: tuple[tuple[float, ...], ...]
    means_original: tuple[tuple[float, ...], ...]
    covariances: tuple[tuple[tuple[float, ...], ...], ...]
    occupancy: tuple[float, ...]
    log_likelihood: float
    bic: float
    n_iter: int
    converged: bool
    version: str = HMM_VERSION

    @property
    def params_hash(self) -> str:
        return stable_hash(self.model_dump(mode="python", exclude={"fit_id"}))

    def _arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        return (
            np.array(self.start_prob),
            np.array(self.transition),
            np.array(self.means_std),
            np.array(self.covariances),
        )

    def _rows(
        self, frame: AsOfFeatureFrame, until: datetime | None = None
    ) -> tuple[list[datetime], np.ndarray]:
        times, x, _ = frame_rows(frame, self.config.features, until=until)
        return times, self.scaler.transform(x)

    def filtered_states(
        self,
        frame: AsOfFeatureFrame,
        *,
        start: datetime | None = None,
        until: datetime | None = None,
    ) -> list[RegimeObservation]:
        """Contemporaneous filtered probabilities for decision times in [start, until]."""
        times, z = self._rows(frame, until)
        if not times:
            return []
        pi, a, mu, cov = self._arrays()
        alpha, _ = _forward(_log_gauss(z, mu, cov), pi, a)
        out: list[RegimeObservation] = []
        for t, probs in zip(times, alpha, strict=True):
            if start is not None and t < start:
                continue
            if t < self.fit_cutoff:
                continue  # in-sample rows are not live states of this fit
            out.append(
                RegimeObservation(
                    as_of=t,
                    fit_id=self.fit_id,
                    model_version=self.version,
                    fit_cutoff=self.fit_cutoff,
                    probability_type=ProbabilityType.FILTERED,
                    kind=StateKind.PROBABILITY_VECTOR,
                    raw_probabilities={i: float(p) for i, p in enumerate(probs / probs.sum())},
                )
            )
        return out

    def smoothed_diagnostics(self, frame: AsOfFeatureFrame) -> list[RegimeObservation]:
        """Future-informed smoothed probabilities over the whole frame (diagnostic only)."""
        times, z = self._rows(frame)
        pi, a, mu, cov = self._arrays()
        logb = _log_gauss(z, mu, cov)
        alpha, log_c = _forward(logb, pi, a)
        gamma = alpha * _backward(logb, a, log_c)
        gamma /= gamma.sum(axis=1, keepdims=True)
        return [
            RegimeObservation(
                as_of=t,
                fit_id=self.fit_id,
                model_version=self.version,
                fit_cutoff=self.fit_cutoff,
                probability_type=ProbabilityType.SMOOTHED,
                kind=StateKind.PROBABILITY_VECTOR,
                raw_probabilities={i: float(p) for i, p in enumerate(g)},
                diagnostic=True,
            )
            for t, g in zip(times, gamma, strict=True)
        ]


def fit_hmm(frame: AsOfFeatureFrame, config: HmmConfig, cutoff: datetime, fit_id: str) -> HmmFit:
    k = config.n_states
    times, x, excluded = training_matrix(
        frame, config.features, cutoff, min_rows=max(k * config.min_rows_per_state, 3)
    )
    scaler = FrozenScaler.fit(config.features, x)
    z = scaler.transform(x)
    t_len, d = z.shape
    init = GaussianMixture(
        n_components=k,
        covariance_type="full",
        random_state=config.seed,
        n_init=3,
        reg_covar=config.reg_covar,
    ).fit(z)
    order = np.argsort(init.means_[:, 0])  # deterministic raw-state order (by first feature)
    mu = init.means_[order].copy()
    cov = init.covariances_[order].copy()
    pi = np.full(k, 1.0 / k)
    a = np.full((k, k), 0.1 / (k - 1))
    np.fill_diagonal(a, 0.9)
    prev_ll = -np.inf
    converged = False
    n_iter = 0
    for iteration in range(1, config.max_iter + 1):
        n_iter = iteration
        logb = _log_gauss(z, mu, cov)
        alpha, log_c = _forward(logb, pi, a)
        beta = _backward(logb, a, log_c)
        ll = float(log_c.sum())
        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True)
        b = np.exp(logb - logb.max(axis=1, keepdims=True))
        scale = np.exp(log_c[1:] - logb[1:].max(axis=1))
        xi = (alpha[:-1, :, None] * a[None] * (b[1:] * beta[1:])[:, None, :]) / scale[:, None, None]
        pi = gamma[0] / gamma[0].sum()
        a = xi.sum(axis=0)
        a /= a.sum(axis=1, keepdims=True)
        w = gamma.sum(axis=0)
        mu = (gamma.T @ z) / w[:, None]
        for j in range(k):
            diff = z - mu[j]
            cov[j] = (gamma[:, j, None] * diff).T @ diff / w[j] + config.reg_covar * np.eye(d)
        if ll - prev_ll < config.tol:
            converged = True
            break
        prev_ll = ll
    logb = _log_gauss(z, mu, cov)
    alpha, log_c = _forward(logb, pi, a)
    gamma = alpha * _backward(logb, a, log_c)
    labels = gamma.argmax(axis=1)
    ll = float(log_c.sum())
    n_params = (k - 1) + k * (k - 1) + k * d + k * d * (d + 1) / 2
    means_orig = mu * np.array(scaler.scales) + np.array(scaler.means)
    return HmmFit(
        fit_id=fit_id,
        config=config,
        fit_cutoff=cutoff,
        train_start=times[0],
        train_end=times[-1],
        n_train=t_len,
        n_excluded_incomplete=excluded,
        scaler=scaler,
        start_prob=tuple(map(float, pi)),
        transition=tuple(tuple(map(float, r)) for r in a),
        means_std=tuple(tuple(map(float, m)) for m in mu),
        means_original=tuple(tuple(map(float, m)) for m in means_orig),
        covariances=tuple(tuple(tuple(map(float, r)) for r in c) for c in cov),
        occupancy=tuple(map(float, np.bincount(labels, minlength=k) / t_len)),
        log_likelihood=ll,
        bic=float(-2 * ll + n_params * np.log(t_len)),
        n_iter=n_iter,
        converged=converged,
    )


def fit_hmm_candidates(
    frame: AsOfFeatureFrame,
    features: Sequence[str],
    candidate_states: Sequence[int],
    cutoff: datetime,
    *,
    seed: int = 0,
    fit_id_prefix: str = "hmm",
) -> list[HmmFit]:
    return [
        fit_hmm(
            frame,
            HmmConfig(features=tuple(features), n_states=k, seed=seed),
            cutoff,
            f"{fit_id_prefix}_k{k}_{cutoff:%Y%m%d}",
        )
        for k in candidate_states
    ]
