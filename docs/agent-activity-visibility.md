# Agent Activity Visibility

This document explains how Claude agent activity is displayed during the `dvsmith build` command.

## Overview

When building Terminal-Bench tasks, Claude agents work autonomously to generate task content. The visibility of agent activity depends on how many agents are running concurrently.

## Display Modes

### Single Agent Mode (Default: `--agent-concurrency 1`)

When running a single agent on a single task, you'll see:

```
Running Claude agent for task: assertion-master_assertions
Agent activity will be logged as it works...

12:29:38.486 | INFO | Flow run 'green-chowchow' - Starting agent for task: assertion-master_assertions
12:29:38.487 | INFO | dvsmith.core.ai_structured - Logging AI calls to: /home/thomas-ahle/.dvsmith/ai_calls.jsonl
12:29:40.123 | INFO | Flow run 'green-chowchow' - [assertion-master_assertions] Reading directory structure
12:29:42.456 | INFO | Flow run 'green-chowchow' - [assertion-master_assertions] Creating task instructions
12:29:45.789 | INFO | Flow run 'green-chowchow' - [assertion-master_assertions] Writing test script
...
12:34:50.028 | INFO | Flow run 'green-chowchow' - Agent completed for assertion-master_assertions: status=ok, tb_check_passed=True
```

**What you see:**
- Initial message about which task is being worked on
- Real-time log messages showing agent activity (tool use, file operations, thinking)
- Completion message with status

### Multi-Agent Mode (`--agent-concurrency > 1`)

When running multiple agents in parallel, you'll see:

```
⠋ Running Claude agents (3 concurrent) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2/5 0:03:15
```

**What you see:**
- Progress bar showing:
  - Spinner animation
  - Number of concurrent agents
  - Tasks completed / total tasks
  - Elapsed time
- Less detailed logging (to avoid overwhelming output with multiple agents)

## Viewing Detailed Activity

### During Execution

For single-agent mode, agent activity is streamed to the console as it happens via Prefect logging.

For multi-agent mode, detailed activity is logged but not displayed to avoid clutter.

### After Execution

All agent activity is automatically logged to `~/.dvsmith/ai_calls.jsonl` regardless of concurrency level.

View the complete agent activity:

```bash
# View the last agent run
dvsmith ai-logs -n 1

# View last 10 agent calls
dvsmith ai-logs -n 10

# View all calls
dvsmith ai-logs --all

# View detailed info for a specific call
dvsmith ai-logs -d 1
```

The logs include:
- Complete conversation history
- All tool uses (Read, Write, Edit, Bash, etc.)
- Thinking process
- Final response
- Duration and timestamps

## What Gets Logged

Each agent activity log entry includes:

- **Prompt**: The task instructions given to Claude
- **System Prompt**: Context about being a Terminal-Bench task builder
- **Messages**: Complete conversation including:
  - Text blocks (agent reasoning)
  - Thinking blocks (extended thinking)
  - Tool use blocks (Read, Write, Edit, Bash commands)
  - Tool result blocks (output from tool execution)
- **Response**: The structured TBAgentResult with:
  - Task ID
  - Status (ok/failed)
  - Modified files list
  - Iterations count
  - TB check results
  - Notes about decisions made
- **Duration**: Time taken in milliseconds
- **Timestamp**: When the call was made

## Troubleshooting

### "I don't see any agent activity"

**For single-agent mode:**
- Check if Prefect logging is working (you should see INFO messages)
- Try running with `DVSMITH_DEBUG=1` for more verbose output
- Agent activity is being captured even if not displayed

**For multi-agent mode:**
- This is expected - progress bar is shown instead
- Use `dvsmith ai-logs` after completion to see details

### "Progress bar is stuck"

- Claude agents can take 3-10 minutes per task
- The spinner should be animating even if progress number doesn't change
- Check `dvsmith ai-logs` to see if agent is actually working
- Large/complex tasks take longer

### "I want to see live feed like in `dvsmith ingest`"

The `ingest` command uses a single AI call with `with_live_agent_feed`, which provides a nice live panel view.

The `build` command may run multiple agents in parallel, making live feed complex. We use logging instead for flexibility.

**Workaround for live-like experience:**
1. Run with `--agent-concurrency 1` (single agent)
2. Watch the log output in real-time
3. Or run `tail -f ~/.dvsmith/ai_calls.jsonl | jq .` in another terminal

## Configuration

### Show More/Less Detail

Control logging verbosity:

```bash
# Standard logging
dvsmith build my-repo

# Verbose logging (shows all DEBUG messages)
DVSMITH_DEBUG=1 dvsmith build my-repo

# Minimal logging (only errors)
dvsmith build my-repo 2>/dev/null
```

### Agent Concurrency Recommendations

- **`-c 1`** (default): Safest for API limits, best visibility
- **`-c 2-3`**: Good balance of speed and cost
- **`-c 5+`**: Fast but expensive, less visible progress

## Examples

### Single task with full visibility
```bash
dvsmith build my-repo --max-tasks 1
```

### Batch with progress bar
```bash
dvsmith build my-repo --max-tasks 10 -c 3
```

### Review activity after batch run
```bash
dvsmith build my-repo -c 5
dvsmith ai-logs -n 20  # See last 20 agent calls
```
