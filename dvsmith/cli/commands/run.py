"""Run command - execute agent with live feed."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from ..agent_runner import run_agent_with_feed


console = Console()


async def run_command(
    agent: Path = typer.Argument(..., help="Path to agent script"),
    task: Path = typer.Argument(..., help="Path to task markdown file"),
    output: Path = typer.Argument(..., help="Output directory for solution"),
    docker: bool = typer.Option(False, "--docker", help="Run in Docker using CVDP harness"),
):
    """Run an agent on a task with live feed display."""
    
    if not agent.exists():
        console.print(f"[red]✗ Agent script not found:[/] {agent}")
        raise typer.Exit(1)
    
    if not task.exists():
        console.print(f"[red]✗ Task file not found:[/] {task}")
        raise typer.Exit(1)
    
    if docker:
        console.print("[yellow]Docker mode not yet implemented. Use direct execution for now.[/]")
        console.print("[dim]TODO: Implement CVDP harness execution[/]")
        # TODO: Implement Docker execution using cvdp.runner.run_harness()
        raise typer.Exit(1)
    
    exit_code = await run_agent_with_feed(agent, task, output, console)
    
    if exit_code != 0:
        raise typer.Exit(exit_code)
