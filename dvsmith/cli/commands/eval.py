"""Eval command - evaluate solutions."""

from pathlib import Path

import typer
from rich.console import Console

from ...config import Profile


console = Console()


def eval_command(
    task: Path = typer.Option(..., "--task", help="Path to task markdown file"),
    patch: Path = typer.Option(..., "--patch", help="Path to solution patch file"),
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """Evaluate a solution patch against a task (placeholder)."""
    
    console.print(f"[cyan]Evaluating solution:[/]")
    console.print(f"  Task: {task}")
    console.print(f"  Patch: {patch}")
    console.print()
    
    if not task.exists():
        console.print(f"[red]✗ Task not found:[/] {task}")
        raise typer.Exit(1)
    
    if not patch.exists():
        console.print(f"[red]✗ Patch not found:[/] {patch}")
        raise typer.Exit(1)
    
    # Check patch file size
    patch_size = patch.stat().st_size
    if patch_size == 0:
        console.print(f"[yellow]⚠ Warning: Patch file is empty (0 bytes)[/]")
        console.print(f"[yellow]  This usually means the agent didn't generate a proper patch.[/]")
        console.print()
        
        # Check for .sv files in same directory
        sv_files = list(patch.parent.glob("*.sv"))
        if sv_files:
            console.print(f"[cyan]Found {len(sv_files)} .sv file(s) in solution directory:[/]")
            for sv in sv_files:
                console.print(f"  • {sv.name}")
            console.print()
            console.print("[yellow]Note: Full eval implementation coming in future version.[/]")
        raise typer.Exit(1)
    
    console.print(f"[green]✓ Patch file size: {patch_size} bytes[/]")
    console.print()
    console.print("[yellow]Note: Full eval implementation coming in future version.[/]")
