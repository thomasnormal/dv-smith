"""Live agent feed utility for CLI commands."""

from collections import deque
from typing import Callable, Any, TypeVar, Awaitable
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel


T = TypeVar('T')


async def with_live_agent_feed(
    async_func: Callable[..., Awaitable[T]],
    console: Console,
    title: str = "Agent Activity",
    max_messages: int = 5,
    *args,
    **kwargs
) -> T:
    """Execute an async function with live agent feed display.
    
    This provides a reusable way to show Claude's activity in real-time
    for any async function that accepts a status_cb parameter.
    
    Args:
        async_func: Async function to execute (must accept status_cb kwarg)
        console: Rich console for output
        title: Title for the live feed panel
        max_messages: Maximum number of recent messages to display
        *args: Positional arguments for async_func
        **kwargs: Keyword arguments for async_func (status_cb will be injected)
        
    Returns:
        Result from async_func
        
    Example:
        ```python
        analyzer = AIRepoAnalyzer(repo_root)
        analysis = await with_live_agent_feed(
            analyzer.analyze,
            console,
            show_progress=False
        )
        ```
    """
    messages = deque(maxlen=max_messages)
    
    def status_callback(msg: str):
        """Capture agent messages."""
        messages.append(msg)
    
    with Live(console=console, refresh_per_second=4) as live:
        def update_display():
            """Update the live display with recent messages."""
            if messages:
                msg_text = "\n".join(f"  {m}" for m in messages)
            else:
                msg_text = "  Starting..."
            
            live.update(Panel(
                msg_text,
                title=f"[cyan]{title}",
                border_style="cyan",
                subtitle="[dim]Live feed from Claude"
            ))
        
        # Initial display
        update_display()
        
        # Create enhanced callback that updates display
        def enhanced_callback(msg: str):
            status_callback(msg)
            update_display()
        
        # Inject status callback into kwargs
        kwargs['status_cb'] = enhanced_callback
        
        # Execute the async function
        result = await async_func(*args, **kwargs)
    
    return result


def create_status_callback(console: Console, title: str = "Processing") -> Callable[[str], None]:
    """Create a simple status callback for cases where you don't want live feed.
    
    This is useful for simpler operations where a spinner is sufficient.
    
    Args:
        console: Rich console
        title: Title prefix for status messages
        
    Returns:
        Callback function that prints status updates
        
    Example:
        ```python
        callback = create_status_callback(console, "Analyzing")
        result = await some_function(status_cb=callback)
        ```
    """
    def callback(msg: str):
        # For now, just ignore - could log or print if needed
        pass
    
    return callback
