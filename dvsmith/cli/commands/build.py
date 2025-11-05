"""Build command - generate a single terminal-bench task."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ...flows.terminal_bench_flow import build_single_terminal_bench_task, preview_available_tasks
from ...core.models import RepoAnalysis

console = Console()

# Configure Prefect logging to be less verbose
os.environ.setdefault("PREFECT_LOGGING_LEVEL", "WARNING")
logging.getLogger("prefect").setLevel(logging.WARNING)


def build_command(
    task_id: str = typer.Argument(..., help="Specific task ID to build (e.g., 'assertion-master_assertions')"),
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Directory for generated terminal-bench task"
    ),
    skip_validation: bool = typer.Option(
        False, "--skip-validation", help="Skip running tb check after generation"
    ),
):
    """Generate a single terminal-bench task using Claude Code SDK."""

    async def run_build() -> None:
        # Extract profile name from task_id (everything before first hyphen)
        # e.g., "assertion-master_assertions" -> look for any profile
        # We'll search all profiles to find which one has this task

        profiles_dir = workspace / "profiles"
        if not profiles_dir.exists():
            console.print(f"[red]No profiles found in:[/] {profiles_dir}")
            console.print("[cyan]Run `dvsmith ingest` first.[/]")
            raise typer.Exit(1)

        # Search for profile containing this task
        profile_name = None
        analysis_path = None
        analysis_data = None

        for profile_dir in profiles_dir.iterdir():
            if not profile_dir.is_dir():
                continue

            candidate_path = profile_dir / "repo_analysis.json"
            if not candidate_path.exists():
                continue

            try:
                candidate_data = json.loads(candidate_path.read_text())
                candidate_analysis = RepoAnalysis.from_dict(candidate_data)
                available_tasks = preview_available_tasks(candidate_analysis)

                if any(t["task_id"] == task_id for t in available_tasks):
                    profile_name = profile_dir.name
                    analysis_path = candidate_path
                    analysis_data = candidate_data
                    break
            except (json.JSONDecodeError, Exception):
                continue

        if not profile_name or not analysis_data:
            console.print(f"[red]Task ID '{task_id}' not found in any profile.[/]")
            console.print("\n[cyan]Available profiles:[/]")
            for profile_dir in profiles_dir.iterdir():
                if profile_dir.is_dir():
                    console.print(f"  • {profile_dir.name}")
            console.print("\n[cyan]List available tasks with:[/]")
            console.print("  dvsmith ingest <repo_url>")
            raise typer.Exit(1)

        console.print(f"[cyan]Found task in profile:[/] {profile_name}")
        console.print(f"[cyan]Using analysis file:[/] {analysis_path}")

        output_dir = output or (workspace / "terminal_bench_tasks" / profile_name)
        output_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"[cyan]Output directory:[/] {output_dir}")
        console.print()

        result = await build_single_terminal_bench_task(
            analysis_data=analysis_data,
            task_id=task_id,
            output_dir=str(output_dir),
            run_validation=not skip_validation,
            console=console,
        )

        # Show results (flow already printed status, so we don't need to repeat)
        task_dir = output_dir / task_id

        if task_dir.exists():
            console.print(f"\n[cyan]Task location:[/] {task_dir}")
            console.print("\n[cyan]Next steps:[/]")
            console.print(f"  # Inspect the task")
            console.print(f"  cd {task_dir}")
            console.print(f"  cat prompt.md")
            console.print(f"\n  # Check task quality")
            console.print(f"  tb tasks check -t {task_id} --tasks-dir {output_dir}")
            console.print(f"\n  # Build Docker image")
            console.print(f"  tb tasks build -t {task_id} --tasks-dir {output_dir}")
            console.print(f"\n  # Run Claude on the task")
            console.print(f"  tb run -t {task_id} --dataset-path {output_dir} -a claude-code")
            console.print()

    asyncio.run(run_build())
