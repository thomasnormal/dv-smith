"""Profile-related commands."""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...core.models import RepoAnalysis

console = Console()


def list_profiles_command(
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """List all available profiles."""
    profiles_dir = workspace / "profiles"
    
    if not profiles_dir.exists():
        console.print("[yellow]No profiles found[/]")
        return
    
    profiles = [p for p in profiles_dir.iterdir() if p.is_dir()]
    
    if not profiles:
        console.print("[yellow]No profiles found[/]")
        return
    
    table = Table(title=f"Available Profiles ({len(profiles)})")
    table.add_column("Name", style="cyan")
    table.add_column("Tests", style="green")
    table.add_column("Simulators", style="yellow")
    
    for prof_dir in sorted(profiles):
        analysis_path = prof_dir / "repo_analysis.json"
        if not analysis_path.exists():
            table.add_row(prof_dir.name, "[red]Invalid[/]", "missing repo_analysis.json")
            continue
        try:
            analysis_data = json.loads(analysis_path.read_text())
            analysis = RepoAnalysis.from_dict(analysis_data)
            simulators = ", ".join(sim.value for sim in analysis.detected_simulators) or "unknown"
            test_count = len(analysis.tests)
            table.add_row(
                prof_dir.name,
                str(test_count),
                simulators,
            )
        except Exception as exc:
            table.add_row(prof_dir.name, "[red]Invalid[/]", str(exc)[:30])
    
    console.print(table)


def validate_profile_command(
    profile_path: Path = typer.Argument(..., help="Path to profile directory or repo_analysis.json"),
):
    """Validate a profile file."""
    if profile_path.is_dir():
        analysis_file = profile_path / "repo_analysis.json"
    else:
        analysis_file = profile_path

    try:
        analysis_data = json.loads(analysis_file.read_text())
        analysis = RepoAnalysis.from_dict(analysis_data)
    except FileNotFoundError:
        console.print(f"[red]repo_analysis.json not found at[/] {analysis_file}")
        raise typer.Exit(1)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid repo_analysis.json:[/] {exc}")
        raise typer.Exit(1)

    analysis_summary = (
        f"Tests: {len(analysis.tests)}\n"
        f"Covergroups: {len(analysis.get_covergroups())}\n"
        f"Assertions: {len(analysis.assertion_files)}"
    )

    console.print(
        Panel.fit(
            f"[green]✓ Profile is valid![/]\n\n"
            f"Repo: {analysis.repo_root or 'unknown'}\n"
            f"Commit: {analysis.git_commit or 'unknown'}\n"
            f"Simulators: {', '.join(sim.value for sim in analysis.detected_simulators) or 'unknown'}\n"
            f"{analysis_summary}",
            title="Profile Validation",
            border_style="green",
        )
    )


def info_command(
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """Show workspace statistics and information."""
    
    # Gather stats
    profiles_dir = workspace / "profiles"
    gyms_dir = workspace / "gyms"
    clones_dir = workspace / "clones"
    
    profile_dirs = [p for p in profiles_dir.iterdir() if p.is_dir()] if profiles_dir.exists() else []
    profile_count = len(profile_dirs)
    gym_count = len(list(gyms_dir.iterdir())) if gyms_dir.exists() else 0
    clone_count = len(list(clones_dir.iterdir())) if clones_dir.exists() else 0
    
    # Calculate total tests
    total_tests = 0
    for prof_dir in profile_dirs:
        analysis_path = prof_dir / "repo_analysis.json"
        if analysis_path.exists():
            try:
                analysis = RepoAnalysis.from_dict(json.loads(analysis_path.read_text()))
                total_tests += len(analysis.tests)
            except Exception:
                pass
    
    # Display info panel
    info_text = f"""[cyan]Workspace:[/] {workspace}

[bold]Profiles:[/] {profile_count}
[bold]Gyms:[/] {gym_count}
[bold]Clones:[/] {clone_count}
[bold]Total Tests:[/] {total_tests}

[bold]AI Logs:[/] ~/.dvsmith/ai_calls.jsonl
[bold]Version:[/] 0.2.0"""
    
    console.print(Panel(info_text, title="DV-Smith Workspace Info", border_style="cyan"))
    
    # Show profile summary if any exist
    if profile_count > 0:
        table = Table(title="Profile Summary")
        table.add_column("Profile", style="cyan")
        table.add_column("Tests", style="green", justify="right")
        table.add_column("Covergroups", style="yellow", justify="right")
        
        for prof_dir in profile_dirs[:10]:
            analysis_path = prof_dir / "repo_analysis.json"
            if not analysis_path.exists():
                continue
            try:
                analysis = RepoAnalysis.from_dict(json.loads(analysis_path.read_text()))
            except Exception:
                continue
            table.add_row(
                prof_dir.name,
                str(len(analysis.tests)),
                str(len(analysis.get_covergroups())),
            )
        
        console.print(table)
