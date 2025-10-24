# Build Command Documentation

The `dvsmith build` command orchestrates the generation of Terminal-Bench tasks from analyzed repositories.

## Overview

The build command takes repository analysis data (from `dvsmith ingest`) and generates Terminal-Bench task scaffolds. Optionally, it can use Claude AI agents to automatically fill in task content.

## Usage

```bash
dvsmith build <profile-name> [OPTIONS]
```

### Basic Examples

```bash
# Generate tasks with AI agent (default: 1 concurrent agent)
dvsmith build my-repo

# Generate with 3 parallel AI agents for faster processing
dvsmith build my-repo --agent-concurrency 3

# Limit to 5 tasks
dvsmith build my-repo --max-tasks 5

# Generate only assertion tasks with 2 parallel agents
dvsmith build my-repo --task-type assertion --agent-concurrency 2
```

## Options

### `--workspace PATH`
Workspace directory containing profiles (default: `./dvsmith_workspace`)

### `--output PATH` / `-o PATH`
Directory for generated Terminal-Bench tasks. Default: `workspace/terminal_bench_tasks/<profile-name>`

### `--max-tasks INT` / `-n INT`
Maximum number of task scaffolds to create. If not specified, generates tasks for all detected candidates.

### `--task-type TEXT` / `-t TEXT`
Task types to generate. Can be specified multiple times. Options:
- `assertion` - Tasks based on assertion files
- `coverage` - Tasks based on coverage files  
- `sequence` - Tasks based on test sequences

Default: All three types

Example: `--task-type assertion --task-type coverage`

### `--skip-validation`
Skip running validation after scaffolding. Useful for faster iteration during development.

### `--agent-concurrency INT` / `-c INT`
Number of Claude agents to run in parallel (default: 1). Higher values speed up generation but use more API quota.

**Recommendations:**
- Start with 1 for testing
- Use 2-3 for balanced speed/cost
- Max 5 for very large batches

## How It Works

### Phase 1: Scaffold Generation
1. Loads repository analysis from `workspace/profiles/<name>/repo_analysis.json`
2. Creates task scaffolds in the output directory
3. Each scaffold includes:
   - Task directory structure
   - Dockerfile template
   - Placeholder files

### Phase 2: AI Agent Generation
1. Claude agents run in parallel (controlled by `--agent-concurrency`)
2. Each agent:
   - Reads the scaffold structure
   - Generates task instructions
   - Creates test scripts
   - Provides reference solutions
   - Runs `tb check .` to validate
   - Iterates until tests pass
3. Progress bar shows agent completion status
4. All agent activity logged to `~/.dvsmith/ai_calls.jsonl`

### Phase 3: Validation (unless `--skip-validation`)
1. Validates each task has required files
2. Reports which tasks pass validation
3. Results saved to `build_summary.json`

## Output

### Directory Structure
```
workspace/terminal_bench_tasks/<profile-name>/
├── assertion-<name-1>/
│   ├── Dockerfile
│   ├── instructions.md
│   ├── run-tests.sh
│   └── solution/
├── coverage-<name-2>/
│   └── ...
└── build_summary.json
```

### Build Summary
The `build_summary.json` file contains:
- Original repository analysis
- Agent results (if `--run-agent` was used)
  - Files modified by each agent
  - Whether `tb check` passed
  - Iteration counts
  - Agent notes
- Validation results
  - Pass/fail status
  - stdout/stderr from `tb check`

## Viewing Agent Activity

```bash
# View last 10 AI agent calls
dvsmith ai-logs

# View all agent activity
dvsmith ai-logs --all

# View detailed info for a specific call
dvsmith ai-logs -d 5
```

## Requirements

- Python 3.12+
- `terminal-bench` installed (automatic via `uv sync`)
- `ANTHROPIC_API_KEY` environment variable set (for `--run-agent`)
- Docker (required by Terminal-Bench)

## Workflow Example

```bash
# 1. Ingest repository
dvsmith ingest https://github.com/user/uvm-testbench my-tb

# 2. Build with AI agents (3 parallel for speed)
dvsmith build my-tb --agent-concurrency 3 --max-tasks 10

# 3. Review agent logs
dvsmith ai-logs -n 30

# 4. Check build summary
cat dvsmith_workspace/terminal_bench_tasks/my-tb/build_summary.json

# 5. Test a generated task manually
cd dvsmith_workspace/terminal_bench_tasks/my-tb/assertion-monitor
tb check .
```

## Troubleshooting

### "tb executable not found"
Install terminal-bench: `uv sync` (should be automatic)

### Agent fails to generate content
- Check `dvsmith ai-logs` for error details
- Ensure `ANTHROPIC_API_KEY` is set
- Try reducing `--agent-concurrency` to 1
- Check that scaffold has sufficient context

### Validation fails but agent reported success
- Independent validation verifies required files exist
- Review `build_summary.json` for details
- Check task directory for generated content

### Out of API quota
- Reduce `--agent-concurrency` to 1 or 2
- Use `--max-tasks` to limit batch size per run
