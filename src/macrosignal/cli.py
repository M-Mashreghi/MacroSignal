"""MacroSignal command-line entry point.

The full command tree is implemented incrementally by the Claude Code task plan.
This bootstrap command intentionally stays minimal so the repository is a valid
installable package from the start.
"""

from __future__ import annotations

import typer

app = typer.Typer(help="MacroSignal research CLI")


@app.command()
def version() -> None:
    """Print the MacroSignal package version."""
    from macrosignal import __version__

    typer.echo(__version__)


@app.command()
def status() -> None:
    """Confirm that the bootstrap CLI is available."""
    typer.echo("MacroSignal bootstrap is ready. Follow docs/PROJECT_PHASES_AND_TASKS.md.")


if __name__ == "__main__":
    app()
