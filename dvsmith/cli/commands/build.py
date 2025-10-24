"""Build command - orchestrate terminal-bench task generation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ...flows.terminal_bench_flow import build_terminal_bench_tasks

console = Console()


def build_command(
    name: str = typer.Argument(..., help="Profile name created via ingest"),
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Directory for generated terminal-bench tasks"
    ),
    max_tasks: Optional[int] = typer.Option(
        None, "--max-tasks", "-n", help="Maximum number of task scaffolds to create"
    ),
    task_type: Optional[list[str]] = typer.Option(
        None,
        "--task-type",
        "-t",
        help="Task types to generate (default: assertion, coverage, sequence)",
    ),
    skip_validation: bool = typer.Option(
        False, "--skip-validation", help="Skip running tb check after scaffolding"
    ),
    agent_concurrency: int = typer.Option(
        1,
        "--agent-concurrency",
        "-c",
        help="Number of Claude agents to run in parallel (default: 1)",
    ),
):
    """Generate terminal-bench task directories using Prefect orchestration."""

    async def run_build() -> None:
        profile_dir = workspace / "profiles" / name
        if not profile_dir.exists():
            console.print(f"[red]Profile not found:[/] {profile_dir}")
            raise typer.Exit(1)

        analysis_path = profile_dir / "repo_analysis.json"
        if not analysis_path.exists():
            console.print(f"[red]Repo analysis not found:[/] {analysis_path}")
            console.print("[cyan]Run `dvsmith ingest` first.[/]")
            raise typer.Exit(1)

        output_dir = output or (workspace / "terminal_bench_tasks" / name)
        output_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"[cyan]Profile directory:[/] {profile_dir}")
        console.print(f"[cyan]Using analysis file:[/] {analysis_path}")
        console.print(f"[cyan]Output directory:[/] {output_dir}")

        task_types = tuple(task_type) if task_type else ("assertion", "coverage", "sequence")

        try:
            analysis_data = json.loads(analysis_path.read_text())
        except json.JSONDecodeError as exc:
            console.print(f"[red]Failed to parse repo_analysis.json:[/] {exc}")
            raise typer.Exit(1)

        result = await build_terminal_bench_tasks(
            analysis_data=analysis_data,
            output_dir=str(output_dir),
            task_types=task_types,
            max_tasks=max_tasks,
            agent_concurrency=agent_concurrency,
            run_validation=not skip_validation,
        )

        summary_path = output_dir / "build_summary.json"
        if summary_path.exists():
            console.print(f"[green]✓ Summary written to[/] {summary_path}")
        else:
            console.print("[yellow]⚠ No summary file generated[/]")

        if result.get("validation_results"):
            passed = [r for r in result["validation_results"] if r.get("passed")]
            console.print(f"[green]✓ Validation passed for {len(passed)} tasks[/]")
        
        # Show helpful information about generated tasks
        console.print("\n[cyan]═══ Generated Tasks ═══[/]")
        console.print(f"[cyan]Location:[/] {output_dir}")
        
        # List task directories
        task_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()])
        if task_dirs:
            console.print(f"\n[cyan]Tasks created:[/]")
            for task_dir in task_dirs:
                console.print(f"  • {task_dir.name}")
            
            console.print(f"\n[cyan]Next steps:[/]")
            console.print(f"  # List all tasks")
            console.print(f"  ls {output_dir}")
            console.print(f"\n  # Inspect a specific task")
            console.print(f"  cd {output_dir}/{task_dirs[0].name}")
            console.print(f"  cat prompt.md")
            console.print(f"\n  # Build Docker image for a task")
            console.print(f"  tb tasks build --task-id {task_dirs[0].name} --tasks-dir {output_dir}")
            console.print(f"\n  # View AI agent activity logs")
            console.print(f"  dvsmith ai-logs -n {len(task_dirs)}")
            console.print()
        else:
            console.print("[yellow]No task directories found[/]")

    asyncio.run(run_build())
