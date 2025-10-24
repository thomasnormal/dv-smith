"""Prefect-based orchestration for building terminal-bench tasks."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Iterable, Literal

from prefect import flow, get_run_logger
from prefect.exceptions import MissingContextError
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from ..core.models import RepoAnalysis
from ..core.terminal_bench_scaffold import TerminalBenchScaffolder, TaskScaffold, slugify


class TBAgentResult(BaseModel):
    """Result from a Terminal-Bench task generation agent."""
    
    task_id: str = Field(description="Task identifier")
    status: Literal["ok", "failed"] = Field(description="Status of the agent run")
    modified_files: list[str] = Field(
        default_factory=list,
        description="List of files modified by the agent"
    )
    iterations: int = Field(default=0, description="Number of iterations the agent took")
    tb_check_passed: bool = Field(
        default=False,
        description="Whether tb check . passed successfully"
    )
    tb_stdout: str = Field(default="", description="Stdout from tb check")
    tb_stderr: str = Field(default="", description="Stderr from tb check")
    notes: str | None = Field(default=None, description="Optional notes or summary")


def _agent_prompt_for_scaffold(scaffold: TaskScaffold) -> str:
    """Build the prompt for the agent to generate a terminal-bench task."""
    return f"""You are generating a complete Terminal-Bench task in the current working directory (cwd): {scaffold.path}

Task Information:
- task_id: {scaffold.task_id}
- task_type: {scaffold.task_type}
- target: {scaffold.target}

Your Goal:
Generate a complete, working Terminal-Bench task that tests DV (Design Verification) skills.

What to Produce:
1. **Instruction file** (instructions.md or README.md):
   - Clear task description for what the user needs to accomplish
   - Specific requirements and success criteria
   - Context about the DV testbench and what's being tested

2. **Test script** (run-tests.sh or test.sh):
   - Executable script that validates task completion
   - Must return exit code 0 on success, non-zero on failure
   - Should be idempotent and compatible with `tb check .`
   - Can test for file existence, output correctness, compilation, etc.

3. **Reference solution** (solution.patch or solution/):
   - Minimal working solution that passes the test
   - Demonstrates the intended approach
   - Can be a patch file or solution directory

How to Work:
1. Start by reading the current directory contents to understand the scaffold structure
2. Use Read/Grep/Glob tools to explore existing files and understand context
3. Create or modify files using Write/Edit tools (work ONLY in cwd: {scaffold.path})
4. After making changes, run `tb tasks build .` using the Bash tool to validate
5. Iterate on failures - read error messages and fix issues
6. Continue until `tb tasks build .` passes successfully

Tool Usage Guidelines:
- Use Read, Write, Edit, Glob, Grep for file operations
- Use Bash ONLY for: `tb tasks build .` and basic shell commands (no network, no installs)
- All file paths are relative to cwd
- Do NOT modify files outside the task directory

Success Criteria:
- `tb tasks build .` passes (exit code 0)
- All required files are present
- Instructions are clear and complete
- Test script properly validates the task
- Reference solution demonstrates a working approach

Final Output:
When done, call the FinalAnswer tool EXACTLY ONCE with a JSON payload matching this structure:
{{
    "task_id": "{scaffold.task_id}",
    "status": "ok",  // or "failed" if you couldn't complete it
    "modified_files": ["file1.md", "run-tests.sh", ...],
    "iterations": <number of times you ran tb check>,
    "tb_check_passed": true,  // or false
    "tb_stdout": "<last tb check output (truncated to 500 chars)>",
    "tb_stderr": "<last tb check errors if any>",
    "notes": "<optional summary of what you created and any decisions made>"
}}
"""


def prepare_task_plans(
    analysis: RepoAnalysis,
    task_types: Iterable[str],
    max_tasks: int | None,
    output_dir: Path,
) -> list[TaskScaffold]:
    """Create scaffolds and return basic plans."""

    remote_url = analysis.git_remote
    commit_sha = analysis.git_commit
    if not remote_url or not commit_sha:
        raise ValueError("Snapshot must include remote_url and commit_sha to scaffold tasks.")

    scaffolder = TerminalBenchScaffolder(
        base_dir=output_dir,
        remote_url=remote_url,
        commit_sha=commit_sha,
    )
    scaffolder.ensure_base()

    def rel_str(path: Path) -> str:
        if analysis.repo_root:
            try:
                return str(path.relative_to(analysis.repo_root))
            except ValueError:
                return str(path)
        return str(path)

    type_to_candidates: dict[str, list[str]] = {
        "assertion": [rel_str(p) for p in analysis.assertion_files],
        "coverage": [rel_str(p) for p in analysis.coverage_files],
        "sequence": [rel_str(p) for p in analysis.test_files],
    }

    plans: list[TaskScaffold] = []
    for task_type in task_types:
        candidates = type_to_candidates.get(task_type, [])
        if not candidates:
            continue
        for candidate in candidates:
            slug_base = slugify(Path(candidate).stem)
            slug = f"{task_type}-{slug_base}"
            existing = {plan.task_id for plan in plans}
            counter = 1
            task_id = slug
            while task_id in existing:
                counter += 1
                task_id = f"{slug}-{counter}"
            scaffold = scaffolder.create_scaffold(
                task_id=task_id,
                task_type=task_type,
                target=candidate,
            )
            plans.append(scaffold)
            if max_tasks and len(plans) >= max_tasks:
                return plans
    return plans


async def _run_agent_with_claude(scaffold: TaskScaffold, logger) -> dict[str, Any]:
    """Run Claude agent to generate a complete terminal-bench task."""
    from ..core.ai_structured import query_with_pydantic_response
    
    logger.info(f"Starting agent for task: {scaffold.task_id}")
    
    prompt = _agent_prompt_for_scaffold(scaffold)
    system_prompt = (
        "You are an expert Terminal-Bench task builder and DV (Design Verification) engineer. "
        "You create clear, well-tested tasks for evaluating AI agents' verification skills. "
        "Work only within the current working directory (cwd). "
        "Use the Bash tool strictly for `tb tasks build .` and basic local shell commands. "
        "No network access. No package installation. "
        "Iterate until tb tasks build passes or you determine the task cannot be completed."
    )
    
    # Create status callback to show agent activity
    def status_callback(msg: str):
        logger.info(f"[{scaffold.task_id}] {msg}")
    
    try:
        result = await query_with_pydantic_response(
            prompt=prompt,
            response_model=TBAgentResult,
            system_prompt=system_prompt,
            cwd=str(scaffold.path),
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", "create_file", "edit_file"],
            status_cb=status_callback,
        )
        
        logger.info(
            f"Agent completed for {scaffold.task_id}: "
            f"status={result.status}, tb_check_passed={result.tb_check_passed}"
        )
        
        return result.model_dump()
        
    except Exception as exc:
        logger.error(f"Agent failed for {scaffold.task_id}: {exc}")
        return {
            "task_id": scaffold.task_id,
            "status": "failed",
            "modified_files": [],
            "iterations": 0,
            "tb_check_passed": False,
            "tb_stdout": "",
            "tb_stderr": "",
            "notes": f"Agent error: {exc}",
        }


async def _run_tb_check(task_dir: Path) -> dict[str, Any]:
    """Check if task scaffold has required files."""
    required_files = ["task.yaml", "Dockerfile", "run-tests.sh"]
    missing_files = []
    
    for filename in required_files:
        if not (task_dir / filename).exists():
            missing_files.append(filename)
    
    if missing_files:
        return {
            "passed": False,
            "stdout": "",
            "stderr": f"Missing required files: {', '.join(missing_files)}",
            "returncode": 1,
        }
    
    return {
        "passed": True,
        "stdout": "Scaffold validation passed: all required files present",
        "stderr": "",
        "returncode": 0,
    }


@flow(name="Build Terminal-Bench Tasks")
async def build_terminal_bench_tasks(
    analysis_data: dict,
    output_dir: str,
    task_types: tuple = ("assertion", "coverage", "sequence"),
    max_tasks: int | None = None,
    agent_concurrency: int = 1,
    run_validation: bool = True,
) -> dict:
    """Main Prefect flow for building terminal-bench tasks."""
    try:
        logger = get_run_logger()
    except MissingContextError:
        logger = logging.getLogger("dvsmith.terminal_bench_flow")

    analysis = RepoAnalysis.from_dict(analysis_data)
    if not analysis.repo_root:
        raise ValueError("RepoAnalysis.repo_root is required")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plans = prepare_task_plans(analysis, task_types, max_tasks, output_dir)
    logger.info("Prepared %d task scaffolds", len(plans))

    # Run Claude agents to generate task content
    agent_results: list[dict[str, Any]] = []
    if len(plans) > 0:
        console = Console()
        
        # For single agent, show more detailed progress; for multiple, show progress bar
        if agent_concurrency == 1 and len(plans) == 1:
            # Single agent - show activity in console without progress bar UI
            console.print(f"[cyan]Running Claude agent for task: {plans[0].task_id}[/cyan]")
            console.print("[dim]Agent activity will be logged as it works...[/dim]\n")
            result = await _run_agent_with_claude(plans[0], logger)
            agent_results = [result]
        else:
            # Multiple agents or tasks - use progress bar
            semaphore = asyncio.Semaphore(agent_concurrency)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task(
                    f"[cyan]Running Claude agents ({agent_concurrency} concurrent)",
                    total=len(plans)
                )

                async def run_single(scaffold: TaskScaffold) -> dict[str, Any]:
                    async with semaphore:
                        result = await _run_agent_with_claude(scaffold, logger)
                        progress.advance(task_id)
                        return result

                agent_results = await asyncio.gather(*(run_single(plan) for plan in plans))
        
        logger.info("Agent stage complete")

    validation_results: list[dict[str, Any]] = []
    if run_validation:
        semaphore = asyncio.Semaphore(2)

        async def validate_single(scaffold: TaskScaffold) -> dict[str, Any]:
            async with semaphore:
                result = await _run_tb_check(scaffold.path)
                result["task_id"] = scaffold.task_id
                return result

        validation_results = await asyncio.gather(*(validate_single(plan) for plan in plans))
        logger.info("Validation stage complete")

    summary_path = output_dir / "build_summary.json"
    summary = {
        "analysis": analysis_data,
        "agent_results": agent_results,
        "validation_results": validation_results,
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    return summary


__all__ = ["build_terminal_bench_tasks"]
