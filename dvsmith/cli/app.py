"""Typer-based CLI for dv-smith with Rich output."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Install rich traceback handler
from rich.traceback import install
install(show_locals=False)

# Disable Claude Code IDE integration hooks
if os.getenv("CLAUDECODE") or os.getenv("AGENT") == "amp":
    os.environ.pop("CLAUDECODE", None)
    os.environ["CLAUDE_NO_IDE"] = "1"

from dotenv import load_dotenv
load_dotenv()

# Import commands
from .commands.ingest import ingest_command
from .commands.build import build_command
from .commands.profile_commands import list_profiles_command, validate_profile_command, info_command
from .commands.run import run_command
from .commands.eval import eval_command

__version__ = "0.2.0"

app = typer.Typer(
    name="dvsmith",
    help="Convert SystemVerilog/UVM testbenches into DV gyms",
    add_completion=False,
)
console = Console()

# Version callback
def version_callback(value: bool):
    if value:
        console.print(f"dvsmith version {__version__}")
        raise typer.Exit()

@app.callback()
def main_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show version"
    ),
):
    """DV-Smith: UVM verification gym builder."""
    pass

# Register commands
app.command(name="ingest")(ingest_command)
app.command(name="build")(build_command)
app.command(name="run")(run_command)
app.command(name="eval")(eval_command)
app.command(name="list-profiles")(list_profiles_command)
app.command(name="validate-profile")(validate_profile_command)
app.command(name="info")(info_command)

# TODO: Add cvdp commands from separate file

def main():
    """Entry point for CLI."""
    app()

if __name__ == "__main__":
    main()
