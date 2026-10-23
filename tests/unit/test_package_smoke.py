"""Package-level smoke tests for the installable MacroSignal scaffold."""

from __future__ import annotations

import re

from typer.testing import CliRunner

import macrosignal
from macrosignal.cli import app

runner = CliRunner()


def test_package_imports_with_version() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", macrosignal.__version__)


def test_cli_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == macrosignal.__version__


def test_cli_status_is_available() -> None:
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "bootstrap" in result.stdout.lower()
