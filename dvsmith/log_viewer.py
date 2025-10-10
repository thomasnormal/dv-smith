"""AI call log visualization utilities."""

import json
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box
from datetime import datetime


def get_log_path() -> Path:
    """Get the AI calls log path."""
    return Path.home() / ".dvsmith" / "ai_calls.jsonl"


def load_ai_calls(log_path: Optional[Path] = None, limit: Optional[int] = None) -> list[dict]:
    """Load AI calls from JSONL log file."""
    if log_path is None:
        log_path = get_log_path()
    
    if not log_path.exists():
        return []
    
    calls = []
    with open(log_path) as f:
        for line in f:
            if line.strip():
                calls.append(json.loads(line))
    
    if limit:
        calls = calls[-limit:]
    
    return calls


def format_duration(duration_ms: float) -> str:
    """Format duration in milliseconds to human-readable format."""
    if duration_ms < 1000:
        return f"{duration_ms:.0f}ms"
    else:
        return f"{duration_ms / 1000:.1f}s"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def display_summary(calls: list[dict], console: Console):
    """Display summary statistics of AI calls."""
    if not calls:
        console.print("[yellow]No AI calls found in log[/yellow]")
        return
    
    total_duration = sum(call.get("duration_ms", 0) for call in calls)
    total_calls = len(calls)
    errors = sum(1 for call in calls if call.get("error"))
    
    # Count by response model type
    model_counts = {}
    for call in calls:
        model = call.get("response_model", "Unknown")
        model_counts[model] = model_counts.get(model, 0) + 1
    
    # Create summary panel
    summary_text = f"""
Total Calls: {total_calls}
Total Duration: {format_duration(total_duration)}
Avg Duration: {format_duration(total_duration / total_calls) if total_calls > 0 else '0ms'}
Errors: {errors}

Call Types:
""" + "\n".join(f"  {model}: {count}" for model, count in sorted(model_counts.items()))
    
    console.print(Panel(summary_text, title="AI Call Log Summary", border_style="cyan"))


def display_calls_conversation(calls: list[dict], console: Console):
    """Display AI calls in a conversation format."""
    if not calls:
        return
    
    for idx, call in enumerate(calls, 1):
        timestamp = call.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("+00:00", ""))
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        model = call.get("response_model", "Unknown")
        duration = format_duration(call.get("duration_ms", 0))
        error = call.get("error")
        
        # Header
        status_icon = "❌" if error else "✓"
        header = f"[bold cyan]Call #{idx}[/bold cyan] | {timestamp} | {model} | {duration} {status_icon}"
        console.print(f"\n{'─' * 80}")
        console.print(header)
        console.print('─' * 80)
        
        # Prompt
        prompt = call.get("prompt", "")
        if prompt:
            console.print("\n[bold yellow]📤 Prompt:[/bold yellow]")
            console.print(prompt)
        
        # Agent Messages (conversation transcript)
        messages = call.get("messages", [])
        if messages:
            console.print("\n[bold magenta]💬 Agent Conversation:[/bold magenta]")
            for msg in messages:
                msg_type = msg.get("type", "unknown")

                if msg_type == "text":
                    text = msg.get("text", "")
                    console.print(f"[cyan]  Agent:[/cyan] {text[:200]}")
                    if len(text) > 200:
                        console.print(f"[dim]    ... ({len(text) - 200} more chars)[/dim]")

                elif msg_type == "thinking":
                    thinking = msg.get("thinking", "")
                    console.print(f"[blue]  💭 Thinking:[/blue] {thinking[:150]}")
                    if len(thinking) > 150:
                        console.print(f"[dim]    ... ({len(thinking) - 150} more chars)[/dim]")

                elif msg_type == "tool_use":
                    tool_name = msg.get("tool_name", "unknown")
                    console.print(f"[green]  🔧 Tool Use:[/green] {tool_name}")
                    tool_input = msg.get("input", {})
                    if tool_input and len(str(tool_input)) < 200:
                        console.print(f"[dim]    Input: {tool_input}[/dim]")

                elif msg_type == "tool_result":
                    content = msg.get("content", "")
                    is_error = msg.get("is_error", False)
                    status = "[red]Error[/red]" if is_error else "[green]Success[/green]"
                    console.print(f"  🔧 Tool Result ({status}): {content[:150]}")
                    if len(content) > 150:
                        console.print(f"[dim]    ... ({len(content) - 150} more chars)[/dim]")

                else:
                    # Unknown message type
                    console.print(f"[dim]  {msg_type}: {str(msg)[:100]}[/dim]")

        # Response or Error
        if error:
            console.print("\n[bold red]❌ Error:[/bold red]")
            console.print(f"[red]{error}[/red]")
        else:
            response = call.get("response", {})
            if response:
                console.print("\n[bold green]📥 Response:[/bold green]")
                response_json = json.dumps(response, indent=2)
                syntax = Syntax(response_json, "json", theme="monokai", line_numbers=False)
                console.print(syntax)

        # Schema (optional, less important)
        schema = call.get("schema")
        if schema:
            console.print("\n[dim]📋 Schema:[/dim]")
            schema_json = json.dumps(schema, indent=2)
            syntax = Syntax(schema_json, "json", theme="monokai", line_numbers=False)
            console.print(syntax)


def display_call_detail(call: dict, console: Console):
    """Display detailed information about a single AI call."""
    timestamp = call.get("timestamp", "Unknown")
    model = call.get("response_model", "Unknown")
    duration = format_duration(call.get("duration_ms", 0))
    
    # Header
    console.print(f"\n[bold cyan]AI Call Details[/bold cyan]")
    console.print(f"Timestamp: {timestamp}")
    console.print(f"Model: {model}")
    console.print(f"Duration: {duration}")
    
    # Prompt
    if call.get("prompt"):
        console.print("\n[bold yellow]Prompt:[/bold yellow]")
        console.print(Panel(call["prompt"], border_style="yellow"))
    
    # Schema
    if call.get("schema"):
        console.print("\n[bold blue]Response Schema:[/bold blue]")
        schema_json = json.dumps(call["schema"], indent=2)
        syntax = Syntax(schema_json, "json", theme="monokai", line_numbers=False)
        console.print(syntax)
    
    # Response
    if call.get("response"):
        console.print("\n[bold green]Response:[/bold green]")
        response_json = json.dumps(call["response"], indent=2)
        syntax = Syntax(response_json, "json", theme="monokai", line_numbers=False)
        console.print(syntax)
    
    # Error
    if call.get("error"):
        console.print("\n[bold red]Error:[/bold red]")
        console.print(Panel(str(call["error"]), border_style="red"))


@click.command()
@click.option("--limit", "-n", type=int, help="Show only the last N calls (default: 10)")
@click.option("--detail", "-d", type=int, help="Show detailed view of call number N")
@click.option("--no-summary", is_flag=True, help="Hide summary statistics")
@click.option("--all", "-a", is_flag=True, help="Show all calls (no limit)")
def show_logs(limit: Optional[int], detail: Optional[int], no_summary: bool, all: bool):
    """View AI call logs with rich formatting."""
    console = Console()
    
    # Determine limit
    if all:
        limit = None
    elif limit is None:
        limit = 10
    
    # Load calls
    calls = load_ai_calls(limit=limit)
    
    if not calls:
        console.print("[yellow]No AI calls found in log[/yellow]")
        return
    
    # Show detail view if requested
    if detail is not None:
        if 1 <= detail <= len(calls):
            display_call_detail(calls[detail - 1], console)
        else:
            console.print(f"[red]Error: Call number {detail} not found. Valid range: 1-{len(calls)}[/red]")
        return
    
    # Show summary unless disabled
    if not no_summary:
        display_summary(calls, console)
    
    # Show conversation
    display_calls_conversation(calls, console)
    
    console.print(f"\n{'─' * 80}")
    console.print(f"[dim]Total: {len(calls)} calls shown | Use --all to see all, -d <N> for specific call[/dim]")


if __name__ == "__main__":
    show_logs()
