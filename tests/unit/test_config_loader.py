"""Typed research-config loading, strictness, and file-reference validation."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from macrosignal.cli import app
from macrosignal.config import ConfigError, load_config_file, load_research_config
from macrosignal.config.models import (
    DailyResearchConfig,
    EventStudyConfig,
    MacroSeriesRegistry,
    RegimeConfig,
    WalkForwardConfig,
)

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_CONFIGS = sorted((ROOT / "configs" / "research").glob("*.yaml"))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """An isolated copy of the committed configs inside a fake project root."""
    shutil.copytree(ROOT / "configs", tmp_path / "configs")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    return tmp_path


def _read(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


# --- valid loads ------------------------------------------------------------------


def test_all_committed_research_configs_are_found() -> None:
    names = {p.name for p in RESEARCH_CONFIGS}
    assert {"demo_daily.yaml", "walk_forward.yaml", "event_study.yaml"} <= names


@pytest.mark.parametrize("path", RESEARCH_CONFIGS, ids=lambda p: p.name)
def test_committed_research_configs_load(path: Path) -> None:
    resolved = load_research_config(path)
    assert resolved.project_root == ROOT
    assert resolved.release_map is not None


def test_demo_daily_loads_typed_objects_and_references() -> None:
    resolved = load_research_config(ROOT / "configs/research/demo_daily.yaml")
    cfg = resolved.config
    assert isinstance(cfg, DailyResearchConfig)
    assert cfg.mode == "free_research"
    assert cfg.expectations.label_output_as == "forecast_error"
    assert cfg.execution.preset == "next_session_close"
    assert cfg.start_date.isoformat() == "2007-01-01"
    assert resolved.macro_registry is not None
    assert "headline_cpi" in resolved.macro_registry.keys
    assert resolved.asset_universe is not None
    assert [a.id for a in resolved.asset_universe.assets][:2] == ["SPY", "QQQ"]
    assert resolved.regime_config is not None
    assert resolved.regime_config.models.hmm.probability_for_signals == "filtered"
    assert resolved.signal_config is not None
    assert set(resolved.references) == {
        "macro_registry", "release_map", "asset_universe", "regime_config", "signal_config",
    }


def test_walk_forward_and_event_study_kinds() -> None:
    wf = load_research_config(ROOT / "configs/research/walk_forward.yaml").config
    es = load_research_config(ROOT / "configs/research/event_study.yaml").config
    assert isinstance(wf, WalkForwardConfig)
    assert wf.split.type == "expanding"
    assert isinstance(es, EventStudyConfig)
    assert es.release_families == ["CPI", "EMPLOYMENT_SITUATION", "PCE", "GDP"]


def test_loading_is_deterministic() -> None:
    path = ROOT / "configs/research/walk_forward.yaml"
    assert load_research_config(path) == load_research_config(path)


def test_loaded_config_is_immutable() -> None:
    cfg = load_research_config(ROOT / "configs/research/demo_daily.yaml").config
    with pytest.raises(Exception, match="frozen"):
        cfg.name = "changed"  # type: ignore[misc]


# --- unknown / invalid fields -----------------------------------------------------


def test_unknown_top_level_field_is_rejected(project: Path) -> None:
    path = project / "configs/research/demo_daily.yaml"
    data = _read(path)
    data["lookahead_ok"] = True
    _write(path, data)
    with pytest.raises(ConfigError, match=r"unknown field 'lookahead_ok'"):
        load_research_config(path)


def test_unknown_nested_field_is_rejected(project: Path) -> None:
    path = project / "configs/research/walk_forward.yaml"
    data = _read(path)
    data["costs"]["base_bsp"] = 5
    _write(path, data)
    with pytest.raises(ConfigError, match=r"unknown field 'costs\.base_bsp'"):
        load_research_config(path)


def test_unknown_field_in_referenced_file_is_rejected(project: Path) -> None:
    regimes = project / "configs/regimes/regimes_v1.yaml"
    data = _read(regimes)
    data["models"]["hmm"]["use_smoothed"] = True
    _write(regimes, data)
    with pytest.raises(ConfigError, match=r"regimes_v1\.yaml[\s\S]*models\.hmm\.use_smoothed"):
        load_research_config(project / "configs/research/demo_daily.yaml")


def test_missing_required_field_is_reported(project: Path) -> None:
    path = project / "configs/research/demo_daily.yaml"
    data = _read(path)
    del data["execution"]
    _write(path, data)
    with pytest.raises(ConfigError, match=r"missing required field 'execution'"):
        load_research_config(path)


def test_missing_or_unknown_kind_is_rejected(project: Path) -> None:
    path = project / "configs/research/demo_daily.yaml"
    data = _read(path)
    data["kind"] = "backtest"
    _write(path, data)
    with pytest.raises(ConfigError, match=r"field 'kind' must be one of"):
        load_research_config(path)


def test_forecast_error_cannot_be_labelled_market_surprise(project: Path) -> None:
    path = project / "configs/research/demo_daily.yaml"
    data = _read(path)
    data["expectations"]["label_output_as"] = "market_surprise"
    _write(path, data)
    with pytest.raises(ConfigError, match=r"never market surprise"):
        load_research_config(path)


def test_smoothed_hmm_probabilities_rejected_for_signals() -> None:
    data = _read(ROOT / "configs/regimes/regimes_v1.yaml")
    data["models"]["hmm"]["probability_for_signals"] = "smoothed"
    from macrosignal.config.loader import validate_mapping

    with pytest.raises(ConfigError, match=r"models\.hmm\.probability_for_signals"):
        validate_mapping(data, RegimeConfig, "regimes.yaml")


def test_unknown_execution_preset_rejected(project: Path) -> None:
    path = project / "configs/research/walk_forward.yaml"
    data = _read(path)
    data["execution"]["preset"] = "same_bar_close"
    _write(path, data)
    with pytest.raises(ConfigError, match=r"execution\.preset"):
        load_research_config(path)


def test_duplicate_series_keys_rejected(tmp_path: Path) -> None:
    data = _read(ROOT / "configs/series/us_macro_v1.yaml")
    data["series"].append(dict(data["series"][0]))
    path = tmp_path / "series.yaml"
    _write(path, data)
    with pytest.raises(ConfigError, match=r"duplicate series keys: \['headline_cpi'\]"):
        load_config_file(path, MacroSeriesRegistry)


def test_invalid_timezone_rejected(project: Path) -> None:
    rmap = project / "configs/series/release_map_v1.yaml"
    data = _read(rmap)
    data["release_families"]["CPI"]["source_timezone"] = "Eastern Standard"
    _write(rmap, data)
    with pytest.raises(ConfigError, match=r"unknown IANA timezone"):
        load_research_config(project / "configs/research/event_study.yaml")


# --- file references --------------------------------------------------------------


def test_missing_referenced_file_is_actionable(project: Path) -> None:
    path = project / "configs/research/demo_daily.yaml"
    data = _read(path)
    data["asset_universe"] = "configs/assets/does_not_exist.yaml"
    _write(path, data)
    with pytest.raises(ConfigError) as info:
        load_research_config(path)
    message = str(info.value)
    assert "field 'asset_universe'" in message
    assert "configs/assets/does_not_exist.yaml" in message
    assert "referenced file not found" in message
    assert "relative to the project root" in message


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("configs/series/us_macro_v1.json", "must point to a .yaml/.yml file"),
        ("../outside.yaml", "escapes the project root"),
    ],
)
def test_invalid_reference_paths_rejected(project: Path, ref: str, expected: str) -> None:
    (project.parent / "outside.yaml").write_text("version: 1\n", encoding="utf-8")
    path = project / "configs/research/walk_forward.yaml"
    data = _read(path)
    data["macro_registry"] = ref
    _write(path, data)
    with pytest.raises(ConfigError, match=expected):
        load_research_config(path)


def test_absolute_reference_path_rejected(project: Path) -> None:
    path = project / "configs/research/walk_forward.yaml"
    data = _read(path)
    data["signal_config"] = str((project / "configs/signals/signals_v1.yaml").resolve())
    _write(path, data)
    with pytest.raises(ConfigError, match=r"must be relative to the project root"):
        load_research_config(path)


def test_series_release_family_must_exist_in_release_map(project: Path) -> None:
    series = project / "configs/series/us_macro_v1.yaml"
    data = _read(series)
    data["series"][0]["release_family"] = "RETAIL_SALES"
    _write(series, data)
    with pytest.raises(ConfigError, match=r"release_family 'RETAIL_SALES'"):
        load_research_config(project / "configs/research/demo_daily.yaml")


def test_event_study_family_must_exist_in_release_map(project: Path) -> None:
    path = project / "configs/research/event_study.yaml"
    data = _read(path)
    data["release_families"].append("RETAIL_SALES")
    _write(path, data)
    with pytest.raises(ConfigError, match=r"event study release family 'RETAIL_SALES'"):
        load_research_config(path)


def test_malformed_yaml_and_non_mapping_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("kind: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML parse error"):
        load_research_config(bad, project_root=tmp_path)
    listing = tmp_path / "list.yaml"
    listing.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="non-empty YAML mapping"):
        load_research_config(listing, project_root=tmp_path)


# --- CLI --------------------------------------------------------------------------


def test_cli_config_validate_success() -> None:
    result = CliRunner().invoke(
        app, ["config", "validate", str(ROOT / "configs/research/demo_daily.yaml")]
    )
    assert result.exit_code == 0, result.output
    assert "OK: daily_research config 'demo_daily_v3'" in result.stdout
    assert "asset_universe: configs/assets/cross_asset_v1.yaml" in result.stdout


def test_cli_config_validate_failure(project: Path) -> None:
    path = project / "configs/research/demo_daily.yaml"
    data = _read(path)
    data["typo_field"] = 1
    _write(path, data)
    result = CliRunner().invoke(app, ["config", "validate", str(path)])
    assert result.exit_code == 1
    assert "unknown field 'typo_field'" in result.output
