"""AI call log viewing command."""

from typing import Optional

import typer
from rich.console import Console

from dvsmith.log_viewer import load_ai_calls, display_summary, display_calls_conversation, display_call_detail


def ai_logs_command(
    limit: Optional[int] = typer.Option(10, "--limit", "-n", help="Show only the last N calls"),
    detail: Optional[int] = typer.Option(None, "--detail", "-d", help="Show detailed view of call number N"),
    no_summary: bool = typer.Option(False, "--no-summary", help="Hide summary statistics"),
    all: bool = typer.Option(False, "--all", "-a", help="Show all calls (no limit)"),
):
    """View AI call logs with rich formatting."""
    console = Console()

    if all:
        limit = None

    calls = load_ai_calls(limit=limit)

    if not calls:
        console.print("[yellow]No AI calls found in log[/yellow]")
        return

    if detail is not None:
        if 1 <= detail <= len(calls):
            display_call_detail(calls[detail - 1], console)
        else:
            console.print(
                f"[red]Error: Call number {detail} not found. Valid range: 1-{len(calls)}[/red]"
            )
        return

    if not no_summary:
        display_summary(calls, console)

    display_calls_conversation(calls, console)

    console.print(f"\n{'─' * 80}")
    console.print(
        f"[dim]Total: {len(calls)} calls shown | Use --all to see all, -d <N> for specific call[/dim]"
    )
