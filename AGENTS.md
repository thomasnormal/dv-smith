# Agent Instructions for DV-Smith

This file helps AI coding agents (like Amp, Cursor, etc.) work effectively with the dv-smith codebase.

## Quick Reference

### Build & Test Commands

```bash
# The project uses uv for package management
uv sync  # Install dependencies including terminal-bench

# Run CLI commands
python -m dvsmith.cli.app --help
python -m dvsmith.cli.app ingest <repo>
python -m dvsmith.cli.app build <profile-name> --agent-concurrency 3
python -m dvsmith.cli.app ai-logs  # View AI agent activity logs

# Run tests
pytest tests/

# Type checking
mypy dvsmith/

# Code formatting
black dvsmith/
ruff check dvsmith/

# Terminal-bench CLI (installed via local dependency)
tb --help
tb check .
```

### Project Structure

- `dvsmith/cli/` - Command-line interface (Typer-based)
- `dvsmith/core/` - Core logic (AI analysis, task generation, models)
- `dvsmith/flows/` - Prefect workflow orchestration
- `terminal-bench/` - Terminal-Bench subproject (local editable dependency)
  - Provides the `tb` CLI tool for task validation

### Dependencies

- **Python 3.12+** required (terminal-bench requirement)
- **terminal-bench** installed as local editable dependency from `terminal-bench/` directory
- Uses `uv` for package management (faster than pip)
- Key dependencies: claude-agent-sdk, anthropic, prefect, typer, rich, pydantic

### Use Test Driven Development

Test first: Whenever I tell you to fix a bug, don't immediately start trying to fix it, instead:
1) Think about what might have caused the bug.
2) Make a unit test (pytest) to try and replicate the bug.
   - The new test should FAIL if you were succesful.
   - Don't make the test too specific, but think about the general assumption that was violated.
   - Keep iterating until you succeed and feel confident that the bug your test triggers
     matches the bug I told you to fix.
3) Only then update the code to actully fix the bug.
4) Check that your solution makes the test PASS.
   Otherwise consider if your test or your solution was wrong.


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

Don't use `from __future__ import ...` we're using python3.12, and if
you're getting errors about annotations, it's likely just that you didn't
enable the venv.


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

