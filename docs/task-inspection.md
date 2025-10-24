# Task Inspection Guide

After running `dvsmith build`, you'll have Terminal-Bench tasks ready to use. This guide shows how to inspect and work with them.

## Finding Your Tasks

Tasks are located in: `dvsmith_workspace/terminal_bench_tasks/<profile-name>/`

```bash
# List all generated tasks
ls dvsmith_workspace/terminal_bench_tasks/axi4_avip/

# Output example:
# assertion-master_assertions/
# coverage-axi4_master_coverage/
# sequence-axi4_base_test/
```

## Task Directory Structure

Each task directory contains:

```
assertion-master_assertions/
├── task.yaml              # Task metadata (difficulty, tags, etc.)
├── prompt.md              # Student-facing instructions
├── instructions.md        # Detailed task description (optional)
├── Dockerfile             # Docker environment setup
├── docker-compose.yaml    # Docker orchestration
├── run-tests.sh           # Test execution script
├── solution.sh            # Reference solution
├── tests/                 # Test files
│   └── test_outputs.py
├── src/                   # Source files (if any)
└── resources/             # Additional resources
    └── setup_repo.sh
```

## Inspecting a Task

### Quick Look

```bash
# Go to task directory
cd dvsmith_workspace/terminal_bench_tasks/axi4_avip/assertion-master_assertions

# Read the student-facing prompt
cat prompt.md

# Read task metadata
cat task.yaml

# Check what tests are included
cat tests/test_outputs.py

# View the reference solution
cat solution.sh
```

### Detailed Inspection

```bash
# View all files
tree .

# Check Dockerfile
cat Dockerfile

# See test script
cat run-tests.sh

# Look at setup resources
cat resources/setup_repo.sh
```

## Using Terminal-Bench Commands

### Build Docker Image

```bash
tb tasks build --task-id assertion-master_assertions \
    --tasks-dir dvsmith_workspace/terminal_bench_tasks/axi4_avip
```

This builds the Docker image for the task.

### Interactive Development

```bash
# Launch interactive shell in task environment
tb tasks interact --task-id assertion-master_assertions \
    --tasks-dir dvsmith_workspace/terminal_bench_tasks/axi4_avip
```

This drops you into a bash shell inside the Docker container where you can:
- Explore the file structure
- Test commands
- Debug issues

### Quality Check

```bash
# Check task quality with LLM
tb tasks check assertion-master_assertions \
    --tasks-dir dvsmith_workspace/terminal_bench_tasks/axi4_avip
```

### Run the Task

```bash
# Run with an AI agent
tb run --agent terminus \
    --model anthropic/claude-3-7-latest \
    --task-id assertion-master_assertions \
    --tasks-dir dvsmith_workspace/terminal_bench_tasks/axi4_avip
```

## Viewing Agent Activity

After `dvsmith build`, all AI agent activity is logged.

### View Last Agent Run

```bash
dvsmith ai-logs -n 1
```

Shows the complete conversation for the last agent including:
- What files it read
- What it wrote
- What commands it ran
- Its reasoning process

### View Multiple Runs

```bash
# Last 5 agent runs
dvsmith ai-logs -n 5

# All runs
dvsmith ai-logs --all

# Detailed view of specific call
dvsmith ai-logs -d 1
```

## Common Inspection Workflows

### "What task should I work on?"

```bash
# List tasks with their prompts
for task in dvsmith_workspace/terminal_bench_tasks/axi4_avip/*/; do
    echo "=== $(basename $task) ==="
    head -5 "$task/prompt.md"
    echo ""
done
```

### "Show me what the agent created"

```bash
cd dvsmith_workspace/terminal_bench_tasks/axi4_avip/assertion-master_assertions

# View the build summary for this specific task
jq '.agent_results[] | select(.task_id == "assertion-master_assertions")' \
    ../build_summary.json
```

### "Did the task pass validation?"

```bash
# Check validation results
jq '.validation_results[] | select(.task_id == "assertion-master_assertions")' \
    dvsmith_workspace/terminal_bench_tasks/axi4_avip/build_summary.json
```

### "What files did the agent modify?"

```bash
# From build summary
jq '.agent_results[] | 
    select(.task_id == "assertion-master_assertions") | 
    .modified_files' \
    dvsmith_workspace/terminal_bench_tasks/axi4_avip/build_summary.json
```

## Task Metadata

### Understanding task.yaml

```yaml
instruction: |-
  Implement SystemVerilog assertions for AXI4 Master protocol...
author_name: DV Smith
author_email: devnull@example.com
difficulty: medium           # easy, medium, hard
category: hardware-verification
tags:
  - systemverilog
  - assertions
  - axi4
parser_name: pytest          # Test output parser
max_agent_timeout_sec: 900   # 15 minutes
max_test_timeout_sec: 180    # 3 minutes
```

### Key Fields

- **instruction**: Short task description shown to agents
- **difficulty**: Complexity level
- **category**: Task classification
- **tags**: Searchable metadata
- **parser_name**: How test results are parsed (pytest, junit, etc.)
- **timeouts**: Limits for agent and test execution

## Tips

### Batch Inspection

```bash
# Count tasks by type
ls dvsmith_workspace/terminal_bench_tasks/axi4_avip/ | \
    grep -oE '^[^-]+' | sort | uniq -c

# Find tasks by difficulty
for task in dvsmith_workspace/terminal_bench_tasks/axi4_avip/*/; do
    diff=$(grep "^difficulty:" "$task/task.yaml" | cut -d: -f2 | tr -d ' ')
    echo "$(basename $task): $diff"
done
```

### Quick Validation

```bash
# Check all tasks have required files
for task in dvsmith_workspace/terminal_bench_tasks/axi4_avip/*/; do
    echo -n "$(basename $task): "
    if [[ -f "$task/task.yaml" ]] && \
       [[ -f "$task/Dockerfile" ]] && \
       [[ -f "$task/run-tests.sh" ]]; then
        echo "✓"
    else
        echo "✗ Missing files"
    fi
done
```

### Diff Tasks

```bash
# Compare two similar tasks
diff -u \
    dvsmith_workspace/terminal_bench_tasks/axi4_avip/assertion-master_assertions/prompt.md \
    dvsmith_workspace/terminal_bench_tasks/axi4_avip/assertion-slave_assertions/prompt.md
```

## Troubleshooting

### "Task directory is empty"

Check if the build actually ran the agent:
```bash
jq '.agent_results' dvsmith_workspace/terminal_bench_tasks/axi4_avip/build_summary.json
```

### "Docker build fails"

Check the Dockerfile for issues:
```bash
cd <task-directory>
docker build -f Dockerfile -t test .
```

### "Tests don't run"

Verify the test script is executable:
```bash
ls -l run-tests.sh
chmod +x run-tests.sh
```

## Next Steps

Once you've inspected your tasks:

1. **Test locally**: Build Docker image and run tests
2. **Refine if needed**: Manually edit task files
3. **Run with agents**: Use `tb run` to test with AI agents
4. **Iterate**: Use `dvsmith build` again with different parameters
