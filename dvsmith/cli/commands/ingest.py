"""Ingest command - capture repository snapshot for terminal-bench generation."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ...core.models import RepoAnalysis
from ...flows.ingest_flow import ingest_repository
from ...flows.terminal_bench_flow import preview_available_tasks

console = Console()

# Configure Prefect logging to be less verbose
os.environ.setdefault("PREFECT_LOGGING_LEVEL", "WARNING")
logging.getLogger("prefect").setLevel(logging.WARNING)


def ingest_command(
    repo_url: str = typer.Argument(..., help="Repository URL or local path"),
    name: Optional[str] = typer.Option(None, help="Profile name (default: derived from repo)"),
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """Analyze a repository and store snapshot metadata."""

    async def run_ingest() -> None:
        profile_name = derive_name(repo_url, name)

        console.print(f"[cyan]Ingesting repository:[/] {repo_url}")
        console.print(f"[cyan]Profile name:[/] {profile_name}")

        # Run Prefect flow
        result = await ingest_repository(
            repo_url=repo_url,
            profile_name=profile_name,
            workspace=workspace,
            console=console,
        )

        # Load analysis for reporting
        analysis = RepoAnalysis.from_dict(result["analysis"])

        # Show warnings if metadata missing
        if not analysis.git_remote:
            console.print(
                "[yellow]⚠ Could not determine git remote. Docker scaffolds require a remote URL for ADD commands.[/]"
            )
        if not analysis.git_commit:
            console.print("[yellow]⚠ Could not determine git commit hash.[/]")

        # Report results
        report_analysis(analysis)
        console.print(f"[green]✓ Analysis saved:[/] {result['analysis_path']}")
        console.print("[green]✓ Ingest complete![/]")

        # Display available tasks
        console.print()
        display_available_tasks(analysis, profile_name)

    asyncio.run(run_ingest())


def derive_name(repo_url: str, explicit_name: Optional[str]) -> str:
    if explicit_name:
        return explicit_name
    if repo_url.startswith(("http://", "https://", "git@")):
        derived = repo_url.rstrip("/").split("/")[-1]
    else:
        derived = Path(repo_url).stem
    return derived.replace(".git", "").replace("-", "_")


def report_analysis(analysis: RepoAnalysis) -> None:
    table = Table(title="Repository Snapshot", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Commit", analysis.git_commit or "unknown")
    table.add_row("Remote", analysis.git_remote or "unknown")
    simulators = ", ".join(sim.value for sim in analysis.detected_simulators) or "none"
    table.add_row("Simulators", simulators)
    table.add_row("Covergroups", str(len(analysis.get_covergroups())))
    table.add_row("Assertion files", str(len(analysis.assertion_files)))
    table.add_row("Coverage files", str(len(analysis.coverage_files)))
    table.add_row("Tests", str(len(analysis.tests)))

    console.print(table)


def display_available_tasks(analysis: RepoAnalysis, profile_name: str) -> None:
    """Display table of available tasks that can be built."""
    available_tasks = preview_available_tasks(analysis)

    if not available_tasks:
        console.print("[yellow]No tasks available to build.[/]")
        return

    table = Table(title=f"Available Tasks ({len(available_tasks)} total)", show_header=True)
    table.add_column("Task ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Target File", style="green")

    for task in available_tasks:
        table.add_row(task["task_id"], task["task_type"], task["target_file"])

    console.print(table)
    console.print()
    console.print("[bold cyan]To build a specific task:[/]")
    console.print(f"  dvsmith build {available_tasks[0]['task_id']}")
    console.print()
    console.print("[dim]Or build multiple tasks with a shell loop:[/]")
    console.print(f"  for task in {available_tasks[0]['task_id']} {available_tasks[1]['task_id'] if len(available_tasks) > 1 else '...'}; do")
    console.print(f"    dvsmith build $task")
    console.print(f"  done")
