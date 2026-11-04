"""Load composite-surprise definitions from config and build the macro composite.

``load_composite_config`` reads ``configs/signals/composite_surprise_*.yaml``
through the typed config loader; ``family_specs(config, mode)`` turns each
family into a :class:`CompositeSpec` for one surprise mode (modes are never
mixed); ``check_against_catalog`` verifies every member feature is a configured
series transformation; ``macro_composite`` combines the family composite values
with the declared family weights, re-normalizing over the families that have a
value and requiring ``min_families``.

The committed v1 config is an a-priori, untuned equal-weight default (see the
file header); alternatives are new variants.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, ConfigDict

from macrosignal.config import load_config_file
from macrosignal.config.models import CompositeSurpriseConfig
from macrosignal.domain import SurpriseMode
from macrosignal.features.series_registry import SeriesCatalog
from macrosignal.surprises.standardize import CompositeSpec, CompositeValue


def load_composite_config(path: Path | str) -> CompositeSurpriseConfig:
    return load_config_file(path, CompositeSurpriseConfig)


def family_specs(config: CompositeSurpriseConfig, mode: SurpriseMode) -> dict[str, CompositeSpec]:
    if mode.value not in config.modes:
        raise ValueError(f"mode {mode.value} is not enabled in {config.variant_id}")
    return {
        family: CompositeSpec(
            name=f"{config.variant_id}__{family}__{mode.value}",
            members=tuple((m.feature, m.weight) for m in spec.members),
            mode=mode,
            max_age_days=spec.max_age_days,
            min_members=spec.min_members,
            signs=tuple((m.feature, m.sign) for m in spec.members if m.sign != 1),
        )
        for family, spec in config.families.items()
    }


def check_against_catalog(config: CompositeSurpriseConfig, catalog: SeriesCatalog) -> None:
    problems: list[str] = []
    for family, spec in config.families.items():
        for m in spec.members:
            key, _, transformation = m.feature.partition("__")
            try:
                series = catalog.get(key)
            except KeyError:
                problems.append(f"{family}: unknown series {key!r}")
                continue
            if transformation not in series.spec.transformation_set:
                problems.append(f"{family}: {key} has no {transformation!r} transformation")
    if problems:
        raise ValueError("; ".join(problems))


class MacroCompositeValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    variant_id: str
    mode: SurpriseMode
    as_of: AwareDatetime
    value: float | None
    family_values: dict[str, float]
    missing_families: tuple[str, ...]


def macro_composite(
    config: CompositeSurpriseConfig,
    family_values: Mapping[str, CompositeValue],
    as_of: datetime,
) -> MacroCompositeValue:
    modes = {v.mode for v in family_values.values()}
    if len(modes) > 1:
        raise ValueError("family composites must share one surprise mode")
    mode = modes.pop() if modes else SurpriseMode(config.modes[0])
    present = {
        f: v.value
        for f, v in family_values.items()
        if v.value is not None and f in config.macro_composite.weights
    }
    missing = tuple(sorted(set(config.macro_composite.weights) - set(present)))
    value = None
    if len(present) >= config.macro_composite.min_families:
        w = {f: config.macro_composite.weights[f] for f in present}
        value = sum(w[f] * present[f] for f in present) / sum(w.values())
    return MacroCompositeValue(
        name=config.macro_composite.name,
        variant_id=config.variant_id,
        mode=mode,
        as_of=as_of,
        value=value,
        family_values=present,
        missing_families=missing,
    )
