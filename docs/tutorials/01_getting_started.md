# Getting Started with DV-Smith

DV-Smith is a framework that converts SystemVerilog/UVM testbenches into containerized verification tasks (DV gyms), similar to SWE-smith/SWE-Gym but for hardware verification.

## Overview

DV-Smith automates the process of:
1. **Analyzing** UVM repositories to discover tests, sequences, and covergroups
2. **Building** DV gyms with isolated tasks for each test
3. **Evaluating** agent solutions based on coverage and health metrics

## Installation

### Prerequisites

- Python 3.8+
- Git
- Anthropic API key (required for AI-powered analysis)
- (Optional) Simulators: Questa/ModelSim, Xcelium, VCS, or Verilator

### Install DV-Smith

```bash
# Clone the repository
git clone https://github.com/yourusername/dv-smith.git
cd dv-smith

# Install with uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Required: Set up Anthropic API key for Claude-powered analysis
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

**Important**: Get your API key from https://console.anthropic.com/settings/keys. The API key is **required** for repository analysis and task generation using Claude 3.5 Sonnet.

## Quick Start

### 1. Ingest a UVM Repository

The first step is to analyze a UVM testbench repository and create a profile:

```bash
# Ingest from GitHub
dvsmith ingest https://github.com/mbits-mirafra/apb_avip --name apb_avip

# Or ingest from local path
dvsmith ingest /path/to/local/repo --name my_bench
```

**What happens during ingest:**
- Claude 3.5 Sonnet analyzes the UVM repository structure
- Discovers tests, sequences, covergroups, and base classes
- Detects build system (Makefile, CMake, etc.)
- Identifies supported simulators
- Creates a profile YAML file in `dvsmith_workspace/profiles/`

**Example output:**
```
[dv-smith] Ingesting repository: https://github.com/mbits-mirafra/apb_avip
[dv-smith] Using Claude 3.5 Sonnet for AI-powered analysis...
[AI Analyzer] Gathering repository structure...
[AI Analyzer] Identifying key directories...
[AI Analyzer] Analyzing test files...
[AI Analyzer] Found 10 tests
[AI Analyzer] Found 12 sequences
[AI Analyzer] Found 2 covergroups
[AI Analyzer] Detected simulators: ['questa', 'vcs', 'xcelium']
[dv-smith] Profile saved to: dvsmith_workspace/profiles/apb_avip.yaml
```

### 2. Build a DV Gym

Once you have a profile, build the gym:

```bash
# Build gym for all detected simulators
dvsmith build apb_avip

# Or specify specific simulators
dvsmith build apb_avip --sim xcelium,questa
```

**What happens during build:**
- Clones/copies the repository
- Removes original test files (keeps them as reference)
- Generates task specifications (Markdown files) for each test
- Sets up smoke tests for validation
- Creates directory structure

**Example output:**
```
[dv-smith] Building gym: apb_avip
[dv-smith] Repository: https://github.com/mbits-mirafra/apb_avip
[TaskGen] Processing 24 tests
[TaskGen] Smoke tests: ['base_test']
[TaskGen] Generated: task_001_8b_write.md
[TaskGen] Generated: task_002_16b_write.md
...
[TaskGen] Generated 23 tasks
[dv-smith] Gym built successfully at: dvsmith_workspace/gyms/apb_avip
```

### 3. Explore the Gym

Your gym is now ready! The directory structure looks like:

```
dvsmith_workspace/
├── profiles/
│   └── apb_avip.yaml          # Profile configuration
├── gyms/
│   └── apb_avip/
│       ├── repo/               # Cloned repository (tests removed)
│       ├── tasks/              # Task specifications
│       │   ├── task_001_8b_write.md
│       │   ├── task_002_16b_write.md
│       │   └── ...
│       ├── smoke_tests/        # Smoke test reference files
│       └── README.md           # Gym information
└── artifacts/                  # Evaluation results (created later)
```

### 4. Read a Task

Tasks are specified in Markdown format:

```bash
cat dvsmith_workspace/gyms/apb_avip/tasks/task_001_8b_write.md
```

Each task includes:
- **Goal**: What functionality to implement
- **Description**: Detailed requirements
- **Hints**: Helpful pointers
- **Acceptance Criteria**: Coverage targets and constraints
- **Scoring Weights**: How the solution will be graded

### 5. Solve a Task (Manual)

To solve a task manually:

1. Navigate to the gym repository:
   ```bash
   cd dvsmith_workspace/gyms/apb_avip/repo
   ```

2. Create your test file in the appropriate directory (see profile for paths)

3. Implement your UVM test and sequences

4. Create a patch file:
   ```bash
   git diff > solution.patch
   ```

### 6. Evaluate a Solution

Once you have a solution (as a patch file), evaluate it:

```bash
dvsmith eval \
    --task dvsmith_workspace/gyms/apb_avip/tasks/task_001_8b_write.md \
    --patch solution.patch \
    --sim xcelium
```

**What happens during evaluation:**
- Applies the patch to a clean gym copy
- Compiles the design with specified simulator
- Runs the simulation with coverage enabled
- Extracts coverage metrics (functional + code)
- Parses simulation logs for errors/warnings
- Calculates weighted score
- Generates detailed evaluation report

**Example output:**
```
[Evaluator] Task: task_001_8b_write
[Evaluator] Applying patch...
[Evaluator] Compiling design...
[Xcelium] Compilation successful
[Evaluator] Running simulation...
[Evaluator] Extracting coverage...
[Evaluator] Coverage: Functional=85.5%, Code=78.2%, Health=100%
[Evaluator] Score: 84.7/100
[Evaluator] Status: PASSED
```

## Common Workflows

### Workflow 1: Test Repository Analysis

```bash
# Ingest multiple repositories
dvsmith ingest https://github.com/mbits-mirafra/apb_avip --name apb
dvsmith ingest https://github.com/mbits-mirafra/axi4_avip --name axi4
dvsmith ingest https://github.com/mbits-mirafra/spi_avip --name spi

# Build all gyms
dvsmith build apb
dvsmith build axi4
dvsmith build spi
```

### Workflow 2: Automated Agent Testing

```bash
# Use the Claude SDK agent (autonomous code generation)
python examples/agents/claude_sdk_agent.py \
    dvsmith_workspace/gyms/apb_avip/tasks/task_008_8b_write.md \
    solutions/task_008

# Evaluate the agent's solution
dvsmith eval \
    --task dvsmith_workspace/gyms/apb_avip/tasks/task_008_8b_write.md \
    --patch solutions/task_008/solution.patch \
    --sim xcelium
```

### Workflow 3: Batch Evaluation

```bash
# Evaluate all tasks in a gym
for task in dvsmith_workspace/gyms/apb_avip/tasks/*.md; do
    task_id=$(basename "$task" .md)
    python your_agent.py "$task" "solutions/$task_id"
    dvsmith eval --task "$task" --patch "solutions/$task_id/solution.patch"
done
```

## Configuration

### Profile Configuration

Profiles are stored in `dvsmith_workspace/profiles/<name>.yaml`:

```yaml
name: apb_avip
repo_path: https://github.com/mbits-mirafra/apb_avip
commit: main

# Discovered information
tests:
  - name: apb_8b_write_test
    file: src/hvlTop/tb/test/apb_8b_write_test.sv
    base_class: base_test

sequences:
  - name: apb_8b_write_seq
    file: src/hvlTop/sequences/apb_8b_write_seq.sv

covergroups:
  - apb_master_coverage.apb_tx_cg

# Build configuration
build:
  questa:
    work_dir: sim/questa_sim
    compile_cmd: make -C sim/questa_sim compile
    run_cmd: make -C sim/questa_sim simulate TEST={test} SEED={seed}
  xcelium:
    work_dir: sim/cadence_sim
    compile_cmd: make -C sim/cadence_sim compile
    run_cmd: make -C sim/cadence_sim simulate TEST={test} SEED={seed}
```

You can manually edit profiles to customize paths and commands.

### Environment Variables

```bash
# Required for AI-powered analysis (Claude 3.5 Sonnet)
ANTHROPIC_API_KEY=your-key-here

# Optional: Simulator paths (if not in PATH)
QUESTA_HOME=/path/to/questa
XCELIUM_HOME=/path/to/xcelium
```

## Troubleshooting

### Issue: AI Analyzer Times Out

**Solution**: Check your API key and network connection:
```bash
# Verify API key is set correctly
echo $ANTHROPIC_API_KEY

# Check if key is in .env file
cat .env | grep ANTHROPIC_API_KEY

# Test API connectivity
python -c "from anthropic import Anthropic; client = Anthropic(); print('API OK')"
```

**Note**: The AI analyzer requires a valid Anthropic API key. Unlike some other tools, DV-Smith does not have a static fallback - AI analysis is essential for accurate repository understanding.

### Issue: No Tests Found

**Possible causes:**
1. Tests use non-standard naming (not `*test*.sv` or `*Test.sv`)
2. Tests are in unexpected directories
3. Repository structure is unusual

**Solution**: Provide hints in a JSON file:
```json
{
    "tests_dir": "custom/path/to/tests",
    "sequences_dir": "custom/path/to/sequences",
    "base_test": "my_custom_base_test"
}
```

Then ingest with hints:
```bash
dvsmith ingest /path/to/repo --name my_bench --hints hints.json
```

### Issue: Compilation Fails

**Check:**
1. Simulator is installed and in PATH
2. Compile command in profile is correct
3. Dependencies are available

**Debug:**
```bash
# Check simulator availability
which xrun  # For Xcelium
which vsim  # For Questa

# Try manual compilation
cd dvsmith_workspace/gyms/<name>/repo
make -C sim/cadence_sim compile
```

## Next Steps

- **[Writing Agents](02_writing_agents.md)**: Learn how to create agents that solve tasks
- **[Understanding Evaluation](03_evaluation.md)**: Deep dive into scoring and metrics
- **[Advanced Usage](04_advanced.md)**: Custom adapters, hooks, and integrations

## Getting Help

- Check the [FAQ](../FAQ.md)
- Open an issue on GitHub
- Join our community discussions