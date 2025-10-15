"""Agent runner with live feed display."""

import asyncio
from pathlib import Path
import re

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from collections import deque


async def run_agent_with_feed(
    agent_script: Path,
    task_file: Path,
    output_dir: Path,
    console: Console,
    max_messages: int = 10
) -> int:
    """Run an agent script with live feed display.
    
    Args:
        agent_script: Path to agent Python script
        task_file: Path to task markdown file
        output_dir: Output directory for solution
        console: Rich console
        max_messages: Max messages to display
        
    Returns:
        Exit code from agent
    """
    messages = deque(maxlen=max_messages)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare command (unbuffered output)
    cmd = ["python3", "-u", str(agent_script), str(task_file), str(output_dir)]
    
    console.print(f"[cyan]Running agent:[/] {agent_script.name}")
    console.print(f"[cyan]Task:[/] {task_file.name}")
    console.print(f"[cyan]Output:[/] {output_dir}")
    console.print("")
    
    # Run agent with live feed
    with Live(console=console, refresh_per_second=4) as live:
        def update_display():
            """Update the live display."""
            if messages:
                msg_text = "\n".join(f"  {m}" for m in messages)
            else:
                msg_text = "  Starting agent..."
            
            live.update(Panel(
                msg_text,
                title="[cyan]Agent Activity",
                border_style="cyan",
                subtitle=f"[dim]{agent_script.name}"
            ))
        
        # Initial display
        update_display()
        
        # Run agent as subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(Path.cwd())
        )
        
        # Stream output
        line_count = 0
        last_update = asyncio.get_event_loop().time()
        
        while True:
            try:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=2.0)
            except asyncio.TimeoutError:
                # Update display even without new lines (shows progress)
                current_time = asyncio.get_event_loop().time()
                if current_time - last_update > 5:
                    messages.append(f"[dim]Running... ({line_count} lines processed)[/dim]")
                    update_display()
                    last_update = current_time
                continue
            
            if not line:
                break
            
            line_text = line.decode('utf-8', errors='ignore').strip()
            line_count += 1
            
            if not line_text:
                continue
            
            # Show ALL lines (not just filtered) but limit display
            # Clean up the line for display
            display_line = line_text
            # Remove ANSI codes if present
            display_line = re.sub(r'\x1b\[[0-9;]*m', '', display_line)
            # Truncate if too long
            if len(display_line) > 90:
                display_line = display_line[:87] + "..."
            
            messages.append(display_line)
            update_display()
            last_update = asyncio.get_event_loop().time()
        
        # Wait for process to complete
        await process.wait()
        return_code = process.returncode
    
    # Show result
    if return_code == 0:
        console.print("\n[green]✓ Agent completed successfully![/]")
        
        # Check for output files
        patch_files = list(output_dir.glob("*.patch"))
        if patch_files:
            console.print(f"[green]✓ Solution patch:[/] {patch_files[0]}")
    else:
        console.print(f"\n[red]✗ Agent failed with exit code {return_code}[/]")
    
    return return_code
