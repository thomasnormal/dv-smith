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

## Practical Examples

### Example 1: Complete Workflow - Analyzing a New Repository

```bash
# Step 1: Ingest a repository
python -m dvsmith.cli.app ingest https://github.com/example/verilog-design

# Step 2: Create a profile (manually edit YAML or use defaults)
# The ingest command creates a basic profile in profiles/

# Step 3: Build tasks with AI analysis
python -m dvsmith.cli.app build verilog-design \
    --agent-concurrency 3 \
    --output-dir runs/$(date +%Y-%m-%d)

# Step 4: Monitor AI agent activity
python -m dvsmith.cli.app ai-logs --tail

# Step 5: Validate generated tasks
tb check runs/$(date +%Y-%m-%d)/tasks/
```

### Example 2: Working with SimVision Waveforms

```python
# dvsmith/skills/simvision_helper.py
from pathlib import Path
from dvsmith.config import get_logger

logger = get_logger(__name__)

async def create_waveform_database(
    design_files: list[Path],
    testbench: Path,
    output_dir: Path,
) -> Path:
    """Create SHM waveform database using SimVision batch mode."""

    # Generate TCL script for database creation
    tcl_script = output_dir / "wave_setup.tcl"
    tcl_script.write_text("""
database -open waves -into waves.shm -default -event
probe -create -all -depth all -database waves testbench
run
exit
""")

    # Run simulation with waveform capture
    import subprocess
    cmd = [
        "xrun",
        "-access", "+rwc",
        "-batch",
        "-input", str(tcl_script),
        *[str(f) for f in design_files],
        str(testbench),
    ]

    result = subprocess.run(cmd, cwd=output_dir, capture_output=True)

    if result.returncode != 0:
        logger.error(f"Simulation failed: {result.stderr.decode()}")
        raise RuntimeError("Waveform generation failed")

    shm_file = output_dir / "waves.shm"
    logger.info(f"Created waveform database: {shm_file}")
    return shm_file


async def convert_to_vcd(shm_file: Path) -> Path:
    """Convert SHM to VCD format for tool interoperability."""
    import subprocess

    vcd_file = shm_file.parent / f"{shm_file.stem}.vcd"
    cmd = [
        "simvisdbutil",
        str(shm_file),
        "-output", str(vcd_file),
        "-vcd",
        "-overwrite",
    ]

    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0:
        raise RuntimeError(f"Conversion failed: {result.stderr.decode()}")

    logger.info(f"Converted to VCD: {vcd_file}")
    return vcd_file
```

### Example 3: Creating a Custom Task Generator

```python
# dvsmith/core/task_generators/custom_tb.py
from pathlib import Path
from typing import AsyncIterator

from dvsmith.config import get_logger
from dvsmith.core.models import Task, TaskMetadata

logger = get_logger(__name__)

class CustomTestbenchGenerator:
    """Generate tasks for custom testbench patterns."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    async def generate_tasks(self) -> AsyncIterator[Task]:
        """Generate tasks by analyzing testbench structure."""

        # Find all testbench files
        tb_files = list(self.repo_root.rglob("*_tb.v"))

        for tb_file in tb_files:
            # Extract module name
            content = tb_file.read_text()
            if match := re.search(r"module\s+(\w+)", content):
                module_name = match.group(1)

                # Generate compilation task
                yield Task(
                    id=f"compile_{module_name}",
                    description=f"Compile {module_name}",
                    command=f"vlog {tb_file.relative_to(self.repo_root)}",
                    metadata=TaskMetadata(
                        category="compile",
                        testbench=tb_file.name,
                        module=module_name,
                    ),
                )

                # Generate simulation task
                yield Task(
                    id=f"simulate_{module_name}",
                    description=f"Simulate {module_name}",
                    command=f"vsim -c {module_name} -do 'run -all; quit'",
                    depends_on=[f"compile_{module_name}"],
                    metadata=TaskMetadata(
                        category="simulate",
                        testbench=tb_file.name,
                        module=module_name,
                    ),
                )

# Usage in a Prefect flow
from dvsmith.flows.build_flow import register_generator

register_generator("custom_tb", CustomTestbenchGenerator)
```

### Example 4: Adding a New CLI Command with Progress Tracking

```python
# In dvsmith/cli/app.py

@app.command()
def analyze_coverage(
    profile_name: str = typer.Argument(..., help="Profile to analyze"),
    run_dir: Path = typer.Option(Path("runs"), "--run-dir", help="Run directory"),
):
    """Analyze coverage from simulation runs."""

    async def run():
        from dvsmith.config import Profile
        from dvsmith.core.coverage import CoverageAnalyzer
        from rich.progress import Progress, SpinnerColumn, TextColumn

        # Load profile
        profile = Profile.from_yaml(f"profiles/{profile_name}.yaml")

        # Find coverage databases
        cov_files = list(run_dir.rglob("*.ucdb"))

        if not cov_files:
            console.print("[red]No coverage files found![/]")
            raise typer.Exit(1)

        # Analyze with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            task = progress.add_task(
                f"Analyzing {len(cov_files)} coverage files...",
                total=len(cov_files),
            )

            analyzer = CoverageAnalyzer(profile)
            results = []

            for cov_file in cov_files:
                result = await analyzer.analyze_file(cov_file)
                results.append(result)
                progress.advance(task)

            # Display summary
            console.print("\n[bold]Coverage Summary[/]")
            for result in results:
                console.print(f"  {result.file}: {result.coverage:.1f}%")

            avg_cov = sum(r.coverage for r in results) / len(results)
            console.print(f"\n[bold green]Average: {avg_cov:.1f}%[/]")

    asyncio.run(run())
```

### Example 5: Testing Async Code with Fixtures

```python
# tests/core/test_analyzer.py
import pytest
from pathlib import Path
from dvsmith.core.ai_analyzer import AIRepoAnalyzer
from dvsmith.core.models import RepoAnalysis

@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    """Create a minimal test repository."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Create sample Verilog file
    (repo / "counter.v").write_text("""
module counter(
    input clk,
    input reset,
    output reg [7:0] count
);
    always @(posedge clk or posedge reset) begin
        if (reset)
            count <= 0;
        else
            count <= count + 1;
    end
endmodule
""")

    # Create testbench
    (repo / "counter_tb.v").write_text("""
module counter_tb;
    reg clk, reset;
    wire [7:0] count;

    counter dut(clk, reset, count);

    initial begin
        $dumpfile("waves.vcd");
        $dumpvars(0, counter_tb);

        clk = 0;
        reset = 1;
        #10 reset = 0;
        #100 $finish;
    end

    always #5 clk = ~clk;
endmodule
""")

    return repo


@pytest.mark.asyncio
async def test_analyzer_finds_modules(test_repo: Path):
    """Test that analyzer identifies Verilog modules."""
    analyzer = AIRepoAnalyzer(repo_root=test_repo)

    result = await analyzer.analyze()

    assert isinstance(result, RepoAnalysis)
    assert len(result.modules) == 2
    assert "counter" in [m.name for m in result.modules]
    assert "counter_tb" in [m.name for m in result.modules]


@pytest.mark.asyncio
async def test_analyzer_generates_tasks(test_repo: Path):
    """Test that analyzer generates appropriate tasks."""
    analyzer = AIRepoAnalyzer(repo_root=test_repo)

    result = await analyzer.analyze()

    # Should generate compile + simulate tasks
    assert len(result.tasks) >= 2

    compile_tasks = [t for t in result.tasks if "compile" in t.id]
    sim_tasks = [t for t in result.tasks if "simulate" in t.id]

    assert len(compile_tasks) > 0
    assert len(sim_tasks) > 0

    # Simulation should depend on compilation
    for sim in sim_tasks:
        assert any(dep in compile_tasks[0].id for dep in sim.depends_on)
```

### Example 6: Using vcdcat for Waveform Analysis

```python
# dvsmith/utils/waveform_analysis.py
import subprocess
from pathlib import Path
from typing import Optional

from dvsmith.config import get_logger

logger = get_logger(__name__)

class VCDAnalyzer:
    """Analyze VCD waveform files using vcdcat."""

    def __init__(self, vcd_file: Path):
        self.vcd_file = vcd_file
        if not vcd_file.exists():
            raise FileNotFoundError(f"VCD file not found: {vcd_file}")

    def list_signals(self, pattern: Optional[str] = None) -> list[str]:
        """List all signals, optionally filtered by pattern."""
        cmd = ["vcdcat", "-l", str(self.vcd_file)]

        if pattern:
            cmd.append(pattern)

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"vcdcat failed: {result.stderr}")
            return []

        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def extract_signal(self, signal_name: str, exact: bool = True) -> dict[int, str]:
        """Extract time-value pairs for a specific signal."""
        cmd = ["vcdcat"]

        if exact:
            cmd.append("-x")

        cmd.extend([str(self.vcd_file), signal_name])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"vcdcat failed: {result.stderr}")
            return {}

        # Parse output (skip header)
        lines = result.stdout.splitlines()
        data_start = next(i for i, line in enumerate(lines) if "====" in line) + 1

        values = {}
        for line in lines[data_start:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                time = int(parts[0])
                value = parts[1]
                values[time] = value

        return values

    def check_signal_toggling(self, signal_name: str, min_toggles: int = 2) -> bool:
        """Verify a signal toggles during simulation."""
        values = self.extract_signal(signal_name)

        if not values:
            logger.warning(f"No data found for signal: {signal_name}")
            return False

        unique_values = set(values.values())
        toggle_count = len(unique_values)

        logger.info(f"Signal {signal_name}: {toggle_count} unique values")
        return toggle_count >= min_toggles


# Usage in a test validation task
async def validate_waveforms(vcd_file: Path, expected_signals: list[str]) -> bool:
    """Validate that expected signals exist and toggle in waveforms."""
    analyzer = VCDAnalyzer(vcd_file)

    # Check all expected signals exist
    all_signals = analyzer.list_signals()

    for expected in expected_signals:
        if not any(expected in sig for sig in all_signals):
            logger.error(f"Expected signal not found: {expected}")
            return False

    # Check clock toggles
    if not analyzer.check_signal_toggling("clk", min_toggles=10):
        logger.error("Clock signal not toggling properly")
        return False

    logger.info("✓ All waveform validations passed")
    return True
```

### Example 7: Prefect Flow with Error Handling

```python
# dvsmith/flows/simulate_flow.py
from pathlib import Path
from prefect import flow, task
from prefect.task_runners import ConcurrentTaskRunner

from dvsmith.config import Profile, get_logger

logger = get_logger(__name__)

@task(retries=2, retry_delay_seconds=5)
async def compile_design(design_file: Path, output_dir: Path) -> bool:
    """Compile a Verilog design file."""
    import subprocess

    logger.info(f"Compiling {design_file.name}")

    result = subprocess.run(
        ["vlog", str(design_file)],
        cwd=output_dir,
        capture_output=True,
    )

    if result.returncode != 0:
        logger.error(f"Compilation failed: {result.stderr.decode()}")
        return False

    logger.info(f"✓ Compiled {design_file.name}")
    return True


@task(retries=1)
async def run_simulation(module_name: str, output_dir: Path) -> Path:
    """Run simulation and generate waveforms."""
    import subprocess

    logger.info(f"Simulating {module_name}")

    # Run with VCD output
    result = subprocess.run(
        ["vsim", "-c", module_name, "-do", "run -all; quit"],
        cwd=output_dir,
        capture_output=True,
    )

    if result.returncode != 0:
        logger.error(f"Simulation failed: {result.stderr.decode()}")
        raise RuntimeError(f"Simulation of {module_name} failed")

    vcd_file = output_dir / "waves.vcd"
    if not vcd_file.exists():
        raise RuntimeError("VCD file not generated")

    logger.info(f"✓ Simulation complete: {vcd_file}")
    return vcd_file


@flow(task_runner=ConcurrentTaskRunner())
async def simulate_all(profile: Profile, output_dir: Path):
    """Run all simulations for a profile."""

    logger.info(f"Starting simulation flow for profile: {profile.name}")

    # Find all design files
    design_files = list(profile.repo_root.rglob("*.v"))
    design_files = [f for f in design_files if not f.name.endswith("_tb.v")]

    # Compile all designs concurrently
    compile_results = []
    for design in design_files:
        result = await compile_design(design, output_dir)
        compile_results.append(result)

    if not all(compile_results):
        logger.error("Some compilations failed")
        return False

    # Find testbenches and simulate
    testbenches = list(profile.repo_root.rglob("*_tb.v"))

    for tb in testbenches:
        module_name = tb.stem  # Remove .v extension
        try:
            vcd_file = await run_simulation(module_name, output_dir)
            logger.info(f"✓ {module_name}: {vcd_file}")
        except Exception as e:
            logger.error(f"✗ {module_name}: {e}")

    logger.info("Simulation flow complete")
    return True
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

