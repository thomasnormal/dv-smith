"""Profile-related commands."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...config import Profile


console = Console()


def list_profiles_command(
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """List all available profiles."""
    profiles_dir = workspace / "profiles"
    
    if not profiles_dir.exists():
        console.print("[yellow]No profiles found[/]")
        return
    
    profiles = list(profiles_dir.glob("*.yaml"))
    
    if not profiles:
        console.print("[yellow]No profiles found[/]")
        return
    
    table = Table(title=f"Available Profiles ({len(profiles)})")
    table.add_column("Name", style="cyan")
    table.add_column("Tests", style="green")
    table.add_column("Simulators", style="yellow")
    
    for prof_file in sorted(profiles):
        try:
            prof = Profile.from_yaml(prof_file)
            table.add_row(
                prof.name,
                str(prof.metadata.test_count),
                ", ".join(prof.simulators[:3])
            )
        except Exception as e:
            table.add_row(prof_file.stem, "[red]Invalid[/]", str(e)[:30])
    
    console.print(table)


def validate_profile_command(
    profile_path: Path = typer.Argument(..., help="Path to profile YAML"),
):
    """Validate a profile file."""
    try:
        profile = Profile.from_yaml(profile_path)
        
        console.print(Panel.fit(
            f"[green]✓ Profile is valid![/]\n\n"
            f"Name: {profile.name}\n"
            f"Tests: {profile.metadata.test_count}\n"
            f"Simulators: {', '.join(profile.simulators)}",
            title="Profile Validation",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]✗ Profile validation failed:[/] {e}")
        raise typer.Exit(1)


def info_command(
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """Show workspace statistics and information."""
    
    # Gather stats
    profiles_dir = workspace / "profiles"
    gyms_dir = workspace / "gyms"
    clones_dir = workspace / "clones"
    
    profile_count = len(list(profiles_dir.glob("*.yaml"))) if profiles_dir.exists() else 0
    gym_count = len(list(gyms_dir.iterdir())) if gyms_dir.exists() else 0
    clone_count = len(list(clones_dir.iterdir())) if clones_dir.exists() else 0
    
    # Calculate total tests
    total_tests = 0
    if profiles_dir.exists():
        for prof_file in profiles_dir.glob("*.yaml"):
            try:
                prof = Profile.from_yaml(prof_file)
                total_tests += prof.metadata.test_count
            except:
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
        
        for prof_file in sorted(profiles_dir.glob("*.yaml"))[:10]:
            try:
                prof = Profile.from_yaml(prof_file)
                table.add_row(
                    prof.name,
                    str(prof.metadata.test_count),
                    str(prof.metadata.covergroup_count)
                )
            except:
                pass
        
        console.print(table)
