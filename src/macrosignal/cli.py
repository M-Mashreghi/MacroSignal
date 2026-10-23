"""MacroSignal command-line entry point.

The full command tree is implemented incrementally by the Claude Code task plan.
This bootstrap command intentionally stays minimal so the repository is a valid
installable package from the start.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="MacroSignal research CLI")
config_app = typer.Typer(help="Inspect and validate configuration files.")
app.add_typer(config_app, name="config")


@app.command()
def version() -> None:
    """Print the MacroSignal package version."""
    from macrosignal import __version__

    typer.echo(__version__)


@app.command()
def status() -> None:
    """Confirm that the bootstrap CLI is available."""
    typer.echo("MacroSignal bootstrap is ready. Follow docs/PROJECT_PHASES_AND_TASKS.md.")


@config_app.command("validate")
def config_validate(
    path: Annotated[
        Path, typer.Argument(help="Research config, e.g. configs/research/demo_daily.yaml")
    ],
) -> None:
    """Validate a research config and every config file it references."""
    from macrosignal.config import ConfigError, load_research_config

    try:
        resolved = load_research_config(path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"OK: {resolved.config.kind} config '{resolved.config.name}'")
    for field, ref in resolved.references.items():
        typer.echo(f"  {field}: {ref.relative_to(resolved.project_root).as_posix()}")


if __name__ == "__main__":
    app()
