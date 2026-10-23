"""Load committed YAML configs into validated, typed objects.

Research configs reference other config files (series registry, release map,
assets, regimes, signals) by paths relative to the project root. The loader
resolves and validates each reference, then checks cross-file consistency.

The loader never reads environment variables: secrets and machine-specific
overrides live in :class:`macrosignal.config.settings.Settings`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from macrosignal.config.models import (
    RESEARCH_KINDS,
    AssetUniverse,
    DailyResearchConfig,
    EventStudyConfig,
    MacroSeriesRegistry,
    RegimeConfig,
    ReleaseMap,
    ResearchConfig,
    SignalConfig,
    WalkForwardConfig,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

PROJECT_ROOT_MARKER = "pyproject.toml"

_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|credential)", re.IGNORECASE
)


class ConfigError(ValueError):
    """A configuration file is missing, malformed, or semantically invalid."""

    def __init__(self, source: Path | str, problems: list[str]) -> None:
        self.source = str(source)
        self.problems = problems
        details = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"Invalid configuration {self.source}:\n{details}")


@dataclass(frozen=True)
class ResolvedResearchConfig:
    """A research config together with every config file it references."""

    path: Path
    project_root: Path
    config: ResearchConfig
    macro_registry: MacroSeriesRegistry | None = None
    release_map: ReleaseMap | None = None
    asset_universe: AssetUniverse | None = None
    regime_config: RegimeConfig | None = None
    signal_config: SignalConfig | None = None

    @property
    def references(self) -> dict[str, Path]:
        """Resolved absolute paths of the referenced config files."""
        return {
            field: (self.project_root / getattr(self.config, field)).resolve()
            for field in _REFERENCE_MODELS
            if hasattr(self.config, field)
        }


def find_project_root(start: Path) -> Path:
    """Return the nearest ancestor of ``start`` that contains ``pyproject.toml``."""
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / PROJECT_ROOT_MARKER).is_file():
            return candidate
    raise ConfigError(
        start,
        [
            f"could not locate the project root (no {PROJECT_ROOT_MARKER} in any parent "
            "directory); pass project_root explicitly"
        ],
    )


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read a YAML file whose top level must be a non-empty mapping."""
    if not path.is_file():
        raise ConfigError(path, ["file not found"])
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(path, [f"YAML parse error: {exc}"]) from exc
    if not isinstance(data, dict) or not data:
        raise ConfigError(path, ["top level must be a non-empty YAML mapping"])
    return data


def _find_secret_keys(data: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            loc = f"{prefix}.{key}" if prefix else str(key)
            if _SECRET_KEY_PATTERN.search(str(key)):
                hits.append(loc)
            hits.extend(_find_secret_keys(value, loc))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            hits.extend(_find_secret_keys(item, f"{prefix}[{i}]"))
    return hits


def _format_validation_error(exc: ValidationError, model: type[BaseModel]) -> list[str]:
    problems = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        if err["type"] == "extra_forbidden":
            problems.append(
                f"unknown field '{loc}': not part of the {model.__name__} schema "
                "(check the spelling or remove it)"
            )
        elif err["type"] == "missing":
            problems.append(f"missing required field '{loc}'")
        else:
            problems.append(f"field '{loc}': {err['msg']} (got {err.get('input')!r})")
    return problems


def validate_mapping(data: dict[str, Any], model: type[ModelT], source: Path | str) -> ModelT:
    """Validate an already-parsed mapping, rejecting secret-like keys first."""
    secrets = _find_secret_keys(data)
    if secrets:
        raise ConfigError(
            source,
            [
                f"secret-like field '{loc}' is not allowed in committed configs; set it "
                "through the environment or .env (MACROSIGNAL_* variables, see "
                "macrosignal.config.settings.Settings)"
                for loc in secrets
            ],
        )
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(source, _format_validation_error(exc, model)) from exc


def load_config_file(path: Path | str, model: type[ModelT]) -> ModelT:
    """Load one YAML config file into ``model``."""
    path = Path(path)
    return validate_mapping(load_yaml_mapping(path), model, path)


def resolve_config_ref(ref: str, field: str, project_root: Path, source: Path) -> Path:
    """Resolve a project-relative config reference, failing with an actionable error."""
    hint = f"field '{field}' -> '{ref}'"
    rel = Path(ref)
    if rel.is_absolute():
        raise ConfigError(source, [f"{hint}: must be relative to the project root"])
    if rel.suffix not in {".yaml", ".yml"}:
        raise ConfigError(source, [f"{hint}: must point to a .yaml/.yml file"])
    root = project_root.resolve()
    resolved = (root / rel).resolve()
    if not resolved.is_relative_to(root):
        raise ConfigError(source, [f"{hint}: escapes the project root {root}"])
    if not resolved.is_file():
        raise ConfigError(
            source,
            [
                f"{hint}: referenced file not found (resolved to {resolved}); paths are "
                f"relative to the project root {root}"
            ],
        )
    return resolved


def _cross_check(resolved: ResolvedResearchConfig) -> list[str]:
    problems: list[str] = []
    release_map = resolved.release_map
    registry = resolved.macro_registry
    if release_map is not None and registry is not None:
        families = set(release_map.release_families)
        for spec in registry.series:
            if spec.release_family is not None and spec.release_family not in families:
                problems.append(
                    f"series '{spec.key}' uses release_family '{spec.release_family}', "
                    f"which is not defined in the release map {sorted(families)}"
                )
        keys = set(registry.keys)
        for name, family in release_map.release_families.items():
            for key in family.series_keys:
                if key not in keys:
                    problems.append(
                        f"release family '{name}' lists series key '{key}', which is not "
                        "defined in the macro series registry"
                    )
    if isinstance(resolved.config, EventStudyConfig) and release_map is not None:
        for name in resolved.config.release_families:
            if name not in release_map.release_families:
                problems.append(
                    f"event study release family '{name}' is not defined in the release map"
                )
    return problems


_REFERENCE_MODELS: dict[str, type[BaseModel]] = {
    "macro_registry": MacroSeriesRegistry,
    "release_map": ReleaseMap,
    "asset_universe": AssetUniverse,
    "regime_config": RegimeConfig,
    "signal_config": SignalConfig,
}


def load_research_config(
    path: Path | str, project_root: Path | str | None = None
) -> ResolvedResearchConfig:
    """Load a ``configs/research/*.yaml`` file and every config it references.

    The top-level ``kind`` field selects the schema (``daily_research``,
    ``walk_forward`` or ``event_study``).
    """
    path = Path(path).resolve()
    root = Path(project_root).resolve() if project_root else find_project_root(path.parent)
    data = load_yaml_mapping(path)

    kind = data.get("kind")
    if kind not in RESEARCH_KINDS:
        raise ConfigError(
            path,
            [f"field 'kind' must be one of {sorted(RESEARCH_KINDS)} (got {kind!r})"],
        )
    config = validate_mapping(data, RESEARCH_KINDS[kind], path)
    assert isinstance(config, DailyResearchConfig | WalkForwardConfig | EventStudyConfig)

    loaded: dict[str, Any] = {}
    for field, model in _REFERENCE_MODELS.items():
        ref = getattr(config, field, None)
        if ref is None:
            continue
        ref_path = resolve_config_ref(ref, field, root, path)
        loaded[field] = load_config_file(ref_path, model)

    resolved = ResolvedResearchConfig(path=path, project_root=root, config=config, **loaded)
    problems = _cross_check(resolved)
    if problems:
        raise ConfigError(path, problems)
    return resolved
