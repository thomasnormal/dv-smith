# CLI Migration Guide

## Overview

dv-smith now has a modernized CLI built with Typer and Rich for better UX and reliability.

## New vs Old CLI

### Entry Points

- **New CLI (recommended)**: `dvsmith` → Uses Typer + Rich
- **Old CLI (deprecated)**: `dvsmith-old` → Original argparse CLI

Both are available during migration. The old CLI will be removed in v1.0.

## Command Comparison

### Ingest a Repository

**Old:**
```bash
dvsmith-old ingest https://github.com/user/repo
```

**New:**
```bash
dvsmith ingest https://github.com/user/repo
```

### List Profiles

**Old:**
```bash
# Not available - had to manually ls dvsmith_workspace/profiles/
```

**New:**
```bash
dvsmith list-profiles

# Beautiful table output:
          Available Profiles (2)
┏━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name     ┃ Tests ┃ Simulators           ┃
┡━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ i3c_avip │ 27    │ vcs, xcelium         │
│ spi_avip │ 1     │ questa, vcs, xcelium │
└──────────┴───────┴──────────────────────┘
```

### Validate Profile

**Old:**
```bash
# Not available - had to manually check YAML
```

**New:**
```bash
dvsmith validate-profile path/to/profile.yaml

# Shows validation panel:
╭─────── Profile Validation ───────╮
│ ✓ Profile is valid!              │
│                                  │
│ Name: spi_avip                   │
│ Tests: 1                         │
│ Simulators: questa, vcs, xcelium │
╰──────────────────────────────────╯
```

## New Features

### 1. Rich Output

- **Colored tables** for structured data
- **Progress spinners** for long operations
- **Panels and boxes** for important info
- **Better error messages** with rich tracebacks

### 2. Type Safety

All profiles are validated using Pydantic:

```python
from dvsmith.config import Profile

# Loads and validates
profile = Profile.from_yaml("profile.yaml")

# Validation errors are clear:
# ValidationError: weights must sum to 1.0, got 0.95
```

### 3. Async Architecture

Library functions are now properly async:

```python
from dvsmith.core.ai_analyzer import AIRepoAnalyzer
import asyncio

async def analyze():
    analyzer = AIRepoAnalyzer(repo_root=Path("./repo"))
    analysis = await analyzer.analyze()  # Async!
    return analysis

result = asyncio.run(analyze())
```

### 4. Reliability

- **Auto-retry**: AI calls retry 3x with exponential backoff
- **Thread-safe logging**: FileLock prevents concurrent write corruption
- **Better error handling**: Rich tracebacks show exactly what went wrong

## Breaking Changes

None! The old CLI is still available and all YAML formats are backwards compatible.

## Migration Checklist

- [ ] Test your workflows with `dvsmith` (new CLI)
- [ ] Update scripts to use `dvsmith` instead of `dvsmith-old`
- [ ] Enjoy better output and reliability!
- [ ] Report any issues before v1.0

## Examples

### Basic Workflow

```bash
# 1. Ingest a repository
dvsmith ingest https://github.com/mbits-mirafra/apb_avip

# 2. List all profiles
dvsmith list-profiles

# 3. Validate a profile
dvsmith validate-profile dvsmith_workspace/profiles/apb_avip.yaml

# 4. Build a gym (coming soon)
dvsmith build apb_avip
```

### Custom Workspace

```bash
dvsmith ingest --workspace /custom/path https://github.com/user/repo
dvsmith list-profiles --workspace /custom/path
```

### Help

```bash
dvsmith --help           # Main help
dvsmith ingest --help    # Command-specific help
dvsmith --version        # Show version
```

## What's Different Internally

### Async All the Way

**Old pattern (bad):**
```python
def analyze(self):
    # Hidden asyncio.run() inside library
    result = asyncio.run(self._async_method())
    return result
```

**New pattern (good):**
```python
async def analyze(self):
    # Async method, caller controls event loop
    result = await self._async_method()
    return result

# CLI calls asyncio.run() at top level
asyncio.run(analyzer.analyze())
```

### Configuration

**Old:**
```python
# Load YAML, hope it's valid
profile = yaml.safe_load(open("profile.yaml"))
```

**New:**
```python
# Pydantic validates everything
profile = Profile.from_yaml("profile.yaml")
# ✓ All fields type-checked
# ✓ Weights sum to 1.0
# ✓ Clear errors on invalid data
```

## Performance

No regression - same ~25-30 second analysis time, but with:
- Better progress feedback
- Prettier output
- More reliable execution

## Support

- New CLI: Full support, active development
- Old CLI: Maintenance only, deprecated in v1.0
