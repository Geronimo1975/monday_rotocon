"""Tests for the Typer CLI entry point.

`cli.py` is a stub today, but it is the `monday` console-script entry point
and the surface real subcommands will hang off of. These tests establish the
`CliRunner` harness now and lock in the stub's documented contract (exit 1
with a "not yet implemented" notice) so a regression is caught the moment the
real implementation lands.
"""

from __future__ import annotations

from typer.testing import CliRunner

from monday_rotocon.cli import app

runner = CliRunner()


def test_stub_command_exits_nonzero() -> None:
    # NOTE: Typer collapses a single-command app, so `ping` is the default
    # callback and runs with no subcommand name. Once a second subcommand is
    # added this becomes `runner.invoke(app, ["ping"])` and `no_args_is_help`
    # starts taking effect — these tests will flag that transition.
    result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert "not yet implemented" in result.output


def test_help_flag_renders_usage() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output
