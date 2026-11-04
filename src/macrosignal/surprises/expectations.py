"""One expectation-provider interface for consensus, model forecasts and proxies.

Every provider declares the single :class:`~macrosignal.domain.ExpectationType`
it supplies and returns typed expectation records (with creation time,
availability and provenance) for a release.  :class:`ExpectationService`
selects, for a release and a :class:`~macrosignal.domain.SurpriseMode`, the
providers of the matching type only, and keeps candidates that

* were available at the query time (``available_at <= as_of``), and
* pass :func:`~macrosignal.domain.check_pre_release` (strictly before the
  actual release; model training cutoff before it as well).

Among valid candidates the most recently available one is chosen; two valid
candidates available at the same instant with different values are ambiguous
and rejected.  No valid candidate means the expectation is **missing** - it is
never imputed.  Rejected candidates are kept with their reasons.

:class:`ExpectationResult` / :func:`expectation_rows` carry ``expectation_type``
and ``mode`` explicitly into every downstream table.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict

from macrosignal.domain import (
    ConsensusExpectation,
    ExpectationChronologyError,
    ExpectationType,
    ModelForecast,
    ProxyExpectation,
    ReleaseEvent,
    SurpriseMode,
    check_pre_release,
)

AnyExpectation = ConsensusExpectation | ModelForecast | ProxyExpectation

MODE_TYPE: dict[SurpriseMode, ExpectationType] = {
    SurpriseMode.MARKET_SURPRISE: ExpectationType.CONSENSUS,
    SurpriseMode.FORECAST_ERROR: ExpectationType.MODEL_FORECAST,
    SurpriseMode.PROXY_SURPRISE: ExpectationType.PROXY,
}


class ExpectationProvider(Protocol):
    name: str
    expectation_type: ExpectationType

    def expectations_for(self, release: ReleaseEvent) -> Sequence[AnyExpectation]: ...


class StaticExpectationProvider:
    """Provider backed by an in-memory list of expectations of one declared type."""

    def __init__(
        self, name: str, expectation_type: ExpectationType, records: Iterable[AnyExpectation]
    ) -> None:
        self.name = name
        self.expectation_type = expectation_type
        self._records = list(records)
        wrong = [r for r in self._records if r.expectation_type is not expectation_type]
        if wrong:
            raise ValueError(
                f"provider {name!r} declares {expectation_type.value} but holds "
                f"{sorted({r.expectation_type.value for r in wrong})}"
            )

    def expectations_for(self, release: ReleaseEvent) -> Sequence[AnyExpectation]:
        return [r for r in self._records if r.release_id == release.release_id]


class ExpectationStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"


class RejectedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    source_snapshot_id: str
    reason: str


class ExpectationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    mode: SurpriseMode
    expectation_type: ExpectationType
    as_of: AwareDatetime
    status: ExpectationStatus
    expectation: AnyExpectation | None = None
    provider: str | None = None
    rejected: tuple[RejectedCandidate, ...] = ()


class AmbiguousExpectationError(ValueError):
    """Several valid expectations became available at the same instant with different values."""


class ExpectationService:
    def __init__(self, providers: Iterable[ExpectationProvider]) -> None:
        self.providers = list(providers)
        names = [p.name for p in self.providers]
        if len(set(names)) != len(names):
            raise ValueError("provider names must be unique")

    def get(self, release: ReleaseEvent, mode: SurpriseMode, as_of: datetime) -> ExpectationResult:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        wanted = MODE_TYPE[mode]
        valid: list[tuple[str, AnyExpectation]] = []
        rejected: list[RejectedCandidate] = []
        for provider in self.providers:
            if provider.expectation_type is not wanted:
                continue
            for exp in provider.expectations_for(release):
                reason: str | None = None
                if exp.expectation_type is not provider.expectation_type:
                    reason = "record type differs from the provider's declared type"
                elif exp.availability.available_at > as_of:
                    reason = "not yet available at the query time"
                else:
                    try:
                        check_pre_release(exp, release, mode)
                    except ExpectationChronologyError as exc:
                        reason = str(exc)
                if reason:
                    rejected.append(
                        RejectedCandidate(
                            provider=provider.name,
                            source_snapshot_id=exp.source_snapshot_id,
                            reason=reason,
                        )
                    )
                else:
                    valid.append((provider.name, exp))
        if not valid:
            return ExpectationResult(
                release_id=release.release_id,
                mode=mode,
                expectation_type=wanted,
                as_of=as_of,
                status=ExpectationStatus.MISSING,
                rejected=tuple(rejected),
            )
        latest_at = max(e.availability.available_at for _, e in valid)
        top = [(p, e) for p, e in valid if e.availability.available_at == latest_at]
        if len({e.expected_value for _, e in top}) > 1:
            raise AmbiguousExpectationError(
                f"{release.release_id}: {len(top)} {wanted.value} expectations available at "
                f"{latest_at.isoformat()} with different values"
            )
        provider_name, chosen = top[0]
        return ExpectationResult(
            release_id=release.release_id,
            mode=mode,
            expectation_type=wanted,
            as_of=as_of,
            status=ExpectationStatus.AVAILABLE,
            expectation=chosen,
            provider=provider_name,
            rejected=tuple(rejected),
        )


def expectation_rows(results: Iterable[ExpectationResult]) -> list[dict[str, Any]]:
    """Flat rows for downstream tables; type and mode are always explicit columns."""
    rows: list[dict[str, Any]] = []
    for r in results:
        e = r.expectation
        rows.append(
            {
                "release_id": r.release_id,
                "mode": r.mode.value,
                "expectation_type": r.expectation_type.value,
                "status": r.status.value,
                "provider": r.provider,
                "expected_value": e.expected_value if e else None,
                "units": e.units if e else None,
                "expectation_available_at": e.availability.available_at if e else None,
                "forecast_created_at": e.forecast_created_at if e else None,
                "expectation_source": e.expectation_source if e else None,
                "source_snapshot_id": e.source_snapshot_id if e else None,
                "model_version": e.model_version if isinstance(e, ModelForecast) else None,
                "n_rejected": len(r.rejected),
            }
        )
    return rows
