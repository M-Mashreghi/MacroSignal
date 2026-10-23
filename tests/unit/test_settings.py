"""Secrets and environment overrides stay separate from committed research configs."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from macrosignal.config import ConfigError, Settings, load_research_config

ROOT = Path(__file__).resolve().parents[2]
ENV_VARS = [
    "MACROSIGNAL_ENV",
    "MACROSIGNAL_DATA_DIR",
    "MACROSIGNAL_REPORTS_DIR",
    "MACROSIGNAL_FRED_API_KEY",
    "MACROSIGNAL_BEA_API_KEY",
    "MACROSIGNAL_MARKET_DATA_API_KEY",
    "FRED_API_KEY",
    "BEA_API_KEY",
    "MARKET_DATA_API_KEY",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_without_environment() -> None:
    settings = Settings(_env_file=None)
    assert settings.env == "development"
    assert settings.data_dir == Path("data")
    assert settings.reports_dir == Path("reports")
    assert settings.fred_api_key is None


def test_prefixed_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MACROSIGNAL_ENV", "test")
    monkeypatch.setenv("MACROSIGNAL_DATA_DIR", "/tmp/macro-data")
    monkeypatch.setenv("MACROSIGNAL_FRED_API_KEY", "prefixed-key")
    settings = Settings(_env_file=None)
    assert settings.env == "test"
    assert settings.data_dir == Path("/tmp/macro-data")
    assert settings.fred_api_key is not None
    assert settings.fred_api_key.get_secret_value() == "prefixed-key"


def test_conventional_key_name_and_prefixed_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEA_API_KEY", "plain-bea")
    monkeypatch.setenv("FRED_API_KEY", "plain-fred")
    monkeypatch.setenv("MACROSIGNAL_FRED_API_KEY", "prefixed-fred")
    settings = Settings(_env_file=None)
    assert settings.bea_api_key is not None
    assert settings.bea_api_key.get_secret_value() == "plain-bea"
    assert settings.fred_api_key is not None
    assert settings.fred_api_key.get_secret_value() == "prefixed-fred"


def test_reads_local_env_file_and_ignores_empty_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MACROSIGNAL_ENV=production\nFRED_API_KEY=from-file\nBEA_API_KEY=\nUNRELATED=1\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=env_file)
    assert settings.env == "production"
    assert settings.fred_api_key is not None
    assert settings.fred_api_key.get_secret_value() == "from-file"
    assert settings.bea_api_key is None


def test_env_example_is_loadable_and_secret_free() -> None:
    settings = Settings(_env_file=ROOT / ".env.example")
    assert settings.env == "development"
    assert settings.fred_api_key is None
    assert settings.bea_api_key is None
    assert settings.market_data_api_key is None


def test_secret_values_are_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "super-secret-value")
    settings = Settings(_env_file=None)
    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings.model_dump())


def test_invalid_env_value_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MACROSIGNAL_ENV", "staging")
    with pytest.raises(ValueError, match="env"):
        Settings(_env_file=None)


def test_research_config_ignores_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    path = ROOT / "configs/research/demo_daily.yaml"
    baseline = load_research_config(path)
    monkeypatch.setenv("MACROSIGNAL_NAME", "overridden")
    monkeypatch.setenv("MACROSIGNAL_EXECUTION__PRESET", "same_day_close")
    monkeypatch.setenv("MACROSIGNAL_FRED_API_KEY", "secret")
    assert load_research_config(path) == baseline


@pytest.mark.parametrize("key", ["fred_api_key", "token", "password"])
def test_secrets_rejected_in_research_config(tmp_path: Path, key: str) -> None:
    data = yaml.safe_load((ROOT / "configs/research/event_study.yaml").read_text("utf-8"))
    data.setdefault("credentials_block", {})[key] = "abc"
    path = tmp_path / "configs" / "research" / "event_study.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ConfigError, match=r"secret-like field .*MACROSIGNAL_"):
        load_research_config(path, project_root=ROOT)


def test_committed_configs_contain_no_secret_like_keys() -> None:
    from macrosignal.config.loader import _find_secret_keys

    for path in sorted((ROOT / "configs").rglob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert _find_secret_keys(data) == [], path
