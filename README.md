# DV-Smith: SystemVerilog/UVM Verification Gym Generator

**DV-Smith** is a framework that automatically converts SystemVerilog/UVM testbenches into containerized verification tasks (DV gyms), enabling AI agents and automated tools to learn and improve hardware verification.

Inspired by [SWE-smith](https://github.com/SWE-Smith/SWE-smith) and [SWE-Gym](https://github.com/SWE-Gym/SWE-Gym), DV-Smith brings the same containerized task paradigm to hardware verification.

## 🎯 What is a DV-Smith?

DV-Smith is a **DV gym generator** that:

- **Analyzes** UVM repositories using AI to discover tests, sequences, and covergroups
- **Builds** isolated verification tasks from existing testbenches
- **Evaluates** solutions based on functional coverage, code coverage, and simulation health
- **Supports** multiple simulators: Xcelium, Questa/ModelSim, VCS, Verilator

### Key Features

✨ **Claude-Powered Analysis**: Uses Claude 3.5 Sonnet to understand any UVM repository structure
🎯 **Automatic Task Generation**: Converts existing tests into isolated tasks with HOWTO guides
📈 **Multi-Metric Evaluation**: Scores solutions on coverage and health metrics
🔌 **Pluggable Simulator Support**: Extensible adapter system for any simulator
🧪 **Comprehensive Testing**: Unit tests, integration tests, and real-world benchmarks
📝 **Intelligent Gym Cleaning**: Uses Claude Code SDK to identify and preserve infrastructure files
🔍 **AI Transparency**: Complete logging of all AI calls with debugging tools (`dvsmith ai-logs`)

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Cadence Xcelium

### Installation

```bash
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

# Required: Set Anthropic API key for Claude-powered analysis
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```


### Create Your First DV Gym

```bash
# 1. Ingest a UVM repository
dvsmith ingest https://github.com/mbits-mirafra/apb_avip

# 2. Build the gym (single simulator)
dvsmith build apb_avip --sim xcelium

# 3. Explore tasks
ls dvsmith_workspace/gyms/apb_avip/tasks/
# You'll see task_001_16b_read.md, task_008_8b_write.md, etc.

# 4. Use Claude SDK agent to solve a task (requires ANTHROPIC_API_KEY)
python examples/agents/claude_sdk_agent.py \
    dvsmith_workspace/gyms/apb_avip/tasks/task_008_8b_write.md \
    solutions/task_008

# 5. Evaluate the solution
dvsmith eval \
    --task dvsmith_workspace/gyms/apb_avip/tasks/task_008_8b_write.md \
    --patch solutions/task_008/solution.patch \
    --sim xcelium
```

## 🔍 AI Transparency & Debugging

DV-Smith provides full transparency into AI operations with built-in logging and debugging tools.

### Debug Logging

Enable verbose debug output to troubleshoot issues or understand what's happening:

```bash
export DVSMITH_DEBUG=1
dvsmith build apb_avip --sim xcelium
```

This will show:
- Detailed compilation commands and simulator invocations
- File operations (copying, removing, etc.)
- AI query details and responses
- Coverage extraction steps
- Infrastructure file analysis

Debug output uses the standard Python logging system and is enabled only when `DVSMITH_DEBUG` is set to `1`, `true`, or `yes`.

### View AI Call Logs

All AI interactions are automatically logged to `~/.dvsmith/ai_calls.jsonl`:

```bash
# View recent AI calls (last 10 by default)
dvsmith ai-logs

# Show more entries
dvsmith ai-logs --tail 20

# Show full details (prompts and responses)
dvsmith ai-logs --tail 5 --full
```

## 📚 Documentation

- **[Getting Started](docs/tutorials/01_getting_started.md)**: Installation, first gym, basic workflows
- **[Writing Agents](docs/tutorials/02_writing_agents.md)**: Create agents that solve verification tasks
- **[Understanding Evaluation](docs/tutorials/03_evaluation.md)**: How solutions are scored

## 📊 Benchmarks

DV-Smith has been tested on public UVM AVIPs:

| Benchmark | Tests Found | Tasks Generated | Covergroups | Simulators | Status |
|-----------|-------------|-----------------|-------------|------------|--------|
| [APB AVIP](https://github.com/mbits-mirafra/apb_avip) | 10 | 9 | 2 | questa, vcs, xcelium | ✅ |
| [AXI4 AVIP](https://github.com/mbits-mirafra/axi4_avip) | 72 | 70 | 2 | xcelium, vcs, questa | ✅ |
| [I3C AVIP](https://github.com/mbits-mirafra/i3c_avip) | 8 | 6 | 2 | questa, vcs, xcelium | ✅ |
| [SPI AVIP](https://github.com/mbits-mirafra/spi_avip) | TBD | TBD | TBD | questa, vcs, xcelium | ⚠️ |

## 🧪 Testing

For debugging, set `DVSMITH_DEBUG=1`

```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_models.py -v                  # Unit tests
pytest tests/test_coverage_parsers.py -v        # Parser tests
pytest tests/test_integration.py -v             # Integration tests

# Run with coverage
pytest tests/ --cov=dvsmith --cov-report=html
```

### Workspace Structure

```
dvsmith_workspace/
├── clones/                # Cloned repositories
│   └── <bench_name>/
├── profiles/              # Repository profiles
│   └── <bench_name>.yaml
└── gyms/                  # Generated DV gyms
    └── <bench_name>/
        ├── tasks/         # Task specifications (*.md)
        ├── HOWTO.md       # Guide for adding new tests
        ├── gym_metadata.yaml
        ├── backups/       # Original test files (for reference)
        ├── work/          # Evaluation artifacts
        │   └── eval/
        │       └── <task_id>/
        │           ├── *.log
        │           └── coverage files
        ├── src/           # Source code (tests removed)
        ├── sim/           # Simulation makefiles
        └── ...            # Other repo files
```

### Task Format

Each task includes a **"Getting Started"** section that directs agents to read the `HOWTO.md` file:

```markdown
## Getting Started
**IMPORTANT:** Before implementing your solution, read the `HOWTO.md` file in the gym root directory.
It contains critical information about:
- How to add tests to the package file (required for compilation)
- UVM test structure and base classes
- Common errors and how to fix them
```

The HOWTO.md guide is automatically generated for each gym and includes:
- Step-by-step instructions for adding new UVM tests
- Package file editing requirements (critical for test registration)
- Common pitfalls and troubleshooting

