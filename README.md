# DV-Smith: SystemVerilog/UVM Verification Gym Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**DV-Smith** is a framework that automatically converts SystemVerilog/UVM testbenches into containerized verification tasks (DV gyms), enabling AI agents and automated tools to learn and improve hardware verification.

Inspired by [SWE-smith](https://github.com/SWE-Smith/SWE-smith) and [SWE-Gym](https://github.com/SWE-Gym/SWE-Gym), DV-Smith brings the same containerized task paradigm to hardware verification.

## 🎯 What is DV-Smith?

DV-Smith is a **DV gym generator** that:

- 📊 **Analyzes** UVM repositories using AI to discover tests, sequences, and covergroups
- 🏗️ **Builds** isolated verification tasks from existing testbenches
- ⚖️ **Evaluates** solutions based on functional coverage, code coverage, and simulation health
- 🔄 **Supports** multiple simulators: Xcelium, Questa/ModelSim, VCS, Verilator

### Key Features

✨ **Claude-Powered Analysis**: Uses Claude 3.5 Sonnet to understand any UVM repository structure
🎯 **Automatic Task Generation**: Converts existing tests into isolated tasks with HOWTO guides
📈 **Multi-Metric Evaluation**: Scores solutions on coverage and health metrics
🔌 **Pluggable Simulator Support**: Extensible adapter system for any simulator
🧪 **Comprehensive Testing**: Unit tests, integration tests, and real-world benchmarks
📝 **Intelligent Gym Cleaning**: Uses Claude Code SDK to identify and preserve infrastructure files

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- One or more EDA simulators:
  - Cadence Xcelium
  - Mentor Questa/ModelSim
  - Synopsys VCS
  - (Verilator support planned)

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

**Important Notes**:
- The `ANTHROPIC_API_KEY` is **required** for repository analysis and task generation
- Get your API key from: https://console.anthropic.com/settings/keys
- Dependencies (`anthropic`, `claude-agent-sdk`, `python-dotenv`) are automatically installed
- If the `dvsmith` command is not found, use `python -m dvsmith.cli` instead

### Create Your First DV Gym

```bash
# 1. Ingest a UVM repository
dvsmith ingest https://github.com/mbits-mirafra/apb_avip --name apb_avip

# 2. Build the gym
dvsmith build apb_avip --sim xcelium

# 3. Explore tasks
ls dvsmith_workspace/gyms/apb_avip/tasks/
# You'll see task_001_16b_read.md, task_008_8b_write.md, etc.

# 4. Use sample agent to solve a task
python examples/agents/simple_agent.py \
    dvsmith_workspace/gyms/apb_avip/tasks/task_008_8b_write.md \
    solutions/task_008

# 5. Evaluate the solution
dvsmith eval \
    --task dvsmith_workspace/gyms/apb_avip/tasks/task_008_8b_write.md \
    --patch solutions/task_008/solution.patch \
    --sim xcelium
```

## 📚 Documentation

- **[Getting Started](docs/tutorials/01_getting_started.md)**: Installation, first gym, basic workflows
- **[Writing Agents](docs/tutorials/02_writing_agents.md)**: Create agents that solve verification tasks
- **[Understanding Evaluation](docs/tutorials/03_evaluation.md)**: How solutions are scored

## 🏗️ Architecture

```
DV-Smith Pipeline:
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│   UVM Repo  │─────▶│  AI Analyzer │─────▶│   Profile    │
└─────────────┘      └──────────────┘      └──────────────┘
                                                    │
                                                    ▼
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│  Evaluation │◀─────│    Agent     │◀─────│   DV Gym     │
└─────────────┘      └──────────────┘      └──────────────┘
```

### Components

**Core:**
- `dvsmith/core/ai_analyzer.py` - Claude-powered repository analysis (Claude 3.5 Sonnet)
- `dvsmith/core/task_generator.py` - Claude-powered task generation (Claude 3.5 Sonnet)
- `dvsmith/core/gym_cleaner.py` - Intelligent gym cleaning (Claude Code SDK)
- `dvsmith/cli.py` - Command-line interface

**Simulator Adapters:**
- `dvsmith/adapters/sim/xcelium.py` - Cadence Xcelium support ✅
- `dvsmith/adapters/sim/questa.py` - Mentor Questa/ModelSim support ✅
- `dvsmith/adapters/sim/base.py` - Base adapter interface

**Coverage Parsers:**
- `dvsmith/adapters/cov/xcelium_parser.py` - Xcelium IMC parser ✅
- `dvsmith/adapters/cov/questa_parser.py` - Questa vcover parser ✅

**Evaluation:**
- `dvsmith/harness/evaluator.py` - Solution evaluation and scoring
- `dvsmith/harness/validator.py` - Gym validation

## 🎯 Example Use Cases

### 1. Benchmark LLM Agents on Hardware Verification

```python
from dvsmith.cli import DVSmith
from my_llm_agent import LLMVerificationAgent

# Create gym from your UVM testbench
dvsmith = DVSmith()
dvsmith.ingest("path/to/your/uvm/repo", name="my_bench")
dvsmith.build("my_bench")

# Evaluate LLM agent on all tasks
agent = LLMVerificationAgent(model="gpt-4")
results = []

for task_file in Path("dvsmith_workspace/gyms/my_bench/tasks").glob("*.md"):
    solution = agent.solve(task_file)
    result = dvsmith.eval(task=task_file, patch=solution)
    results.append(result)

print(f"Pass rate: {sum(r.passed for r in results) / len(results):.1%}")
```

### 2. Automated Test Generation Research

```bash
# Generate training dataset
for repo in repo_list.txt; do
    dvsmith ingest "$repo" --name $(basename "$repo")
    dvsmith build $(basename "$repo")
done

# Train your model on generated tasks
python train_model.py --data dvsmith_workspace/gyms/*/tasks/*.md
```

### 3. Continuous Verification Testing

```bash
# CI/CD integration
dvsmith ingest . --name ci_gym
dvsmith build ci_gym --sim xcelium
dvsmith validate ci_gym  # Ensure smoke tests pass

# Evaluate changes
dvsmith eval --task gym/tasks/task_001.md --patch pr_changes.patch
```

## 📊 Benchmarks

DV-Smith has been tested on public UVM AVIPs:

| Benchmark | Tests Found | Tasks Generated | Covergroups | Simulators | Status |
|-----------|-------------|-----------------|-------------|------------|--------|
| [APB AVIP](https://github.com/mbits-mirafra/apb_avip) | 10 | 9 | 2 | questa, vcs, xcelium | ✅ |
| [AXI4 AVIP](https://github.com/mbits-mirafra/axi4_avip) | 72 | 70 | 2 | xcelium, vcs, questa | ✅ |
| [I3C AVIP](https://github.com/mbits-mirafra/i3c_avip) | TBD | TBD | TBD | questa, vcs | 🔄 |
| [SPI AVIP](https://github.com/mbits-mirafra/spi_avip) | TBD | TBD | TBD | questa, vcs, xcelium | 🔄 |

## 🧪 Testing

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

**Test Results:**
- ✅ 21/23 unit tests passing (91%)
- ✅ 4/4 integration tests passing (100%)
- ✅ Xcelium adapter fully tested
- ✅ Coverage parsers validated

## 🔧 Configuration

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

### Profile Configuration

Profiles are automatically generated but can be customized:

```yaml
name: apb_avip
repo_url: dvsmith_workspace/clones/apb_avip
description: UVM testbench for apb_avip
simulators:
  - questa
  - vcs
  - xcelium

paths:
  root: .
  tests: src/hvl_top/test
  sequences: src/hvl_top/test/sequences
  env: src/hvl_top/env

build:
  xcelium:
    work_dir: sim/cadence_sim
    compile_cmd: make -C sim/cadence_sim compile
    run_cmd: make -C sim/cadence_sim simulate test={test} SEED={seed}

coverage:
  questa:
    report_cmd: vcover report -details -output {output} {ucdb}
    functional_covergroups:
      - apb_master_coverage.apb_master_covergroup
      - apb_slave_coverage.apb_slave_covergroup

grading:
  smoke_tests:
    - apb_base_test
  weights:
    functional_coverage: 0.6
    code_coverage: 0.3
    health: 0.1
  thresholds:
    functional:
      min_pct: 80.0
      strategy: any_of
    code:
      statements_min_pct: 70.0
      branches_min_pct: 60.0
      toggles_min_pct: 50.0
    health:
      max_uvm_errors: 0
      max_uvm_fatals: 0
      max_scoreboard_errors: 0
      all_assertions_pass: true
```

## 🤝 Contributing

We welcome contributions! Areas of interest:

- 🔌 New simulator adapters (VCS, Verilator, DSIM)
- 🤖 Sample agents (LLM-based, template-based, search-based)
- 📊 Additional benchmarks
- 🧪 Test coverage improvements
- 📚 Documentation and tutorials

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [SWE-smith](https://github.com/SWE-Smith/SWE-smith) and [SWE-Gym](https://github.com/SWE-Gym/SWE-Gym)
- Test repositories from [mbits-mirafra](https://github.com/mbits-mirafra)
- UVM methodology from Accellera

## 📞 Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/yourusername/dv-smith/issues)
- 💬 [Discussions](https://github.com/yourusername/dv-smith/discussions)

## 🗺️ Roadmap

- [x] Core framework and CLI
- [x] AI-powered repository analysis
- [x] Questa adapter + coverage parser
- [x] Xcelium adapter + coverage parser
- [x] Task generator with markdown format
- [x] Validation and evaluation harnesses
- [x] Comprehensive unit and integration tests
- [x] Sample agent implementation
- [x] Complete documentation and tutorials
- [ ] VCS simulator adapter
- [ ] Verilator adapter with coverage
- [ ] Docker containerization for reproducibility
- [ ] Web UI for gym exploration
- [ ] Integration with popular LLM frameworks
- [ ] Benchmark leaderboard
- [ ] Support for SystemC/TLM testbenches

---

**Built for the hardware verification community by the hardware verification community.**