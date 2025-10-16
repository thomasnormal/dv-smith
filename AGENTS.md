# Agent Instructions for DV-Smith

This file helps AI coding agents (like Amp, Cursor, etc.) work effectively with the dv-smith codebase.

## Quick Reference

### Build & Test Commands

```bash
# The project uses uv for package management
uv pip install -e .

# Run tests
pytest tests/

# Type checking
mypy dvsmith/

# Code formatting
black dvsmith/
ruff check dvsmith/
```

### Running the CLI

```bash
# New Typer CLI (preferred)
python -m dvsmith.cli.app --help
python -m dvsmith.cli.app ingest <repo-url>
python -m dvsmith.cli.app list-profiles

# Old CLI (deprecated, but still works)
python -m dvsmith.cli --help
```

## Architecture

### Async Pattern

**Libraries should be async:**
```python
# ✅ Good: Async library function
async def analyze(self) -> RepoAnalysis:
    result = await some_async_operation()
    return result

# ❌ Bad: asyncio.run() inside library
def analyze(self) -> RepoAnalysis:
    return asyncio.run(self._async_method())
```

**CLI calls asyncio.run() at top level:**
```python
# ✅ Good: CLI handles event loop
@app.command()
def my_command():
    async def run():
        analyzer = AIRepoAnalyzer(repo)
        result = await analyzer.analyze()
        return result
    
    asyncio.run(run())
```

### Configuration

Use Pydantic models for all config:

```python
from dvsmith.config import Profile

# ✅ Type-checked loading
profile = Profile.from_yaml("profile.yaml")

# ❌ Avoid raw YAML
profile = yaml.safe_load(open("profile.yaml"))
```

## Code Style

### Imports

**IMPORTANT: All imports must be at the top of the file.**

```python
# Standard library (alphabetical)
import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional

# Third-party (alphabetical)
import typer
from pydantic import BaseModel
from rich.console import Console

# Local (alphabetical by module, then by import)
from ..config import Profile
from ..core.models import RepoAnalysis
from .live_feed import with_live_agent_feed
```

**Rules:**
- ✅ All imports at the top (no imports inside functions)
- ✅ Group by: stdlib, third-party, local
- ✅ Alphabetical within each group
- ✅ Absolute imports for local code (from ...package import)
- ❌ Never import inside functions (except for type checking)

### Logging

Use the configured logger, not print:

```python
from dvsmith.config import get_logger

logger = get_logger(__name__)

# ✅ Good
logger.info("Processing...")
logger.warning("Cache miss")
logger.error("Failed to parse")

# ❌ Avoid
print("[INFO] Processing...")
```

The logger automatically works with tqdm progress bars via TqdmLoggingHandler.

### Error Handling

Use domain-specific exceptions where appropriate:

```python
# Current: Generic exceptions
raise ValueError("Invalid simulator")

# Future: Domain exceptions  
raise SimulatorNotAvailable(f"Simulator {name} not found")
```

## Testing Patterns

### Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_analyze():
    analyzer = AIRepoAnalyzer(repo_root=Path("/tmp/repo"))
    result = await analyzer.analyze()
    assert len(result.tests) > 0
```

### Profile Fixtures

```python
@pytest.fixture
def sample_profile():
    return Profile(
        name="test",
        repo_url="/tmp/test",
        simulators=["questa"],
        paths={"root": ".", "tests": "tests"},
        # ... minimal required fields
    )
```

## Common Tasks

### Adding a New CLI Command

1. Open `dvsmith/cli/app.py`
2. Add a new command function:

```python
@app.command()
def my_command(
    arg: str = typer.Argument(..., help="Some argument"),
    option: bool = typer.Option(False, "--opt", help="Some option"),
):
    """Command description shown in help."""
    
    async def run():
        # Your async logic here
        console.print("[green]Success![/]")
    
    asyncio.run(run())
```

### Adding a New Simulator Adapter

1. Create `dvsmith/adapters/sim/my_simulator.py`
2. Implement `SimulatorAdapter` interface
3. Register in `dvsmith/adapters/sim/__init__.py`:

```python
from .my_simulator import MySimulatorAdapter

SimulatorRegistry.register(Simulator.MY_SIM, MySimulatorAdapter)
```

### Making a Function Async

When you need to call async functions:

```python
# 1. Make your function async
async def my_function():
    result = await some_async_call()
    return result

# 2. Update callers to await it
result = await my_function()

# 3. If caller is at top level (CLI), use asyncio.run()
asyncio.run(my_function())
```

## File Structure

```
dvsmith/
├── cli/                    # CLI commands (Typer)
│   ├── __init__.py
│   └── app.py             # Main Typer app
├── config/                # Configuration
│   ├── __init__.py
│   ├── logging.py         # Logging setup
│   └── schemas.py         # Pydantic models
├── core/                  # Core domain logic
│   ├── ai_analyzer.py     # AI-powered analysis (ASYNC)
│   ├── ai_structured.py   # Pydantic AI calls (ASYNC)
│   ├── models.py          # Data models
│   └── task_generator.py  # Task generation
├── adapters/              # Simulator/tool adapters
│   ├── sim/              # Simulator adapters
│   └── cov/              # Coverage adapters
└── harness/              # Evaluation harness
```

## Dependencies

### Core
- `claude-agent-sdk` - AI agent SDK
- `anthropic` - Anthropic API
- `pydantic` - Data validation
- `pydantic-settings` - Config validation

### CLI & UX
- `typer` - CLI framework
- `rich` - Terminal formatting
- `tqdm` - Progress bars

### Reliability
- `tenacity` - Retry logic
- `filelock` - Thread-safe file operations

## Conventions

1. **Async by default** in library code
2. **Type hints everywhere** - helps IDEs and mypy
3. **Pydantic for data** - validation + serialization
4. **Rich for CLI output** - no raw print() statements
5. **Logger over print** - use configured logger

## AI-Specific Notes

When working with AI calls:

- All AI calls are in `dvsmith/core/ai_structured.py`
- They automatically retry on transient failures
- Logging to `~/.dvsmith/ai_calls.jsonl` is thread-safe
- Use `query_with_pydantic_response()` for structured responses

## Questions?

Check:
- `docs/CLI_MIGRATION.md` - CLI migration guide
- `docs/claude-code-sdk.md` - Claude SDK documentation  
- `docs/testbenches.md` - Available test benches
