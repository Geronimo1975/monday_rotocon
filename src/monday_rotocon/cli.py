"""Typer CLI for monday_rotocon.

Stub: the real subcommands (`ping`, `boards list`, `export dashboard`) are
implemented in later tasks. This file exists so the `[project.scripts]`
entry in `pyproject.toml` resolves cleanly throughout development.
"""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, help="monday_rotocon CLI")


@app.command()
def ping() -> None:  # pragma: no cover — replaced in Task 12
    """Placeholder; replaced by the real implementation in Task 12."""
    typer.echo("monday_rotocon CLI not yet implemented. See plan Task 12.")
    raise typer.Exit(code=1)
