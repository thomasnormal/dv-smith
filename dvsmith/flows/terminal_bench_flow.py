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
   - If you depend on pytest, install it inside the container before running (for example with `uv pip install pytest`); otherwise, implement the checker using only the Python standard library.
   - IMPORTANT: When using pytest, ALWAYS use the `-ra` flag (e.g., `pytest "$TEST_DIR/test_outputs.py" -ra`) to ensure the test summary is parseable by terminal-bench, even when all tests pass.

3. **Reference solution** (solution.patch or solution/):
   - Minimal working solution that passes the test
   - Demonstrates the intended approach
   - Can be a patch file or solution directory

How to Work:
1. Start by reading the current directory contents to understand the scaffold structure
2. Use Read/Grep/Glob tools to explore existing files and understand context
3. Create or modify files using Write/Edit tools (work ONLY in cwd: {scaffold.path})
4. After making changes, validate using the Bash tool:
   - Run: `cd .. && tb tasks check {scaffold.task_id} --tasks-dir .`
   - This checks task quality including instruction clarity, test alignment, anti-cheating measures
5. Read the quality check output carefully - it shows pass/fail for each criterion with explanations
6. Fix any failures by updating task files (prompt.md, task.yaml, tests/, etc.)
7. Re-run the check and iterate until all quality checks pass
8. Optionally also run: `cd .. && tb tasks build {scaffold.task_id} --tasks-dir .` to test Docker build

Tool Usage Guidelines:
- Use Read, Write, Edit, Glob, Grep for file operations
- Use Bash for: `tb tasks check` and `tb tasks build` validation commands
- All file paths are relative to cwd
- Do NOT modify files outside the task directory

Success Criteria:
- `tb tasks check` shows all quality checks passing (or only acceptable failures)
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
    "iterations": <number of times you ran tb tasks check>,
    "tb_check_passed": true,  // whether tb tasks check passed (all checks green/pass)
    "tb_stdout": "<last tb tasks check output (truncated to 500 chars)>",
    "tb_stderr": "<errors if any>",
    "notes": "<summary of what you created, quality check results, and any known limitations>"
}}
"""


def preview_available_tasks(analysis: RepoAnalysis) -> list[dict[str, str]]:
    """Preview all available tasks without creating scaffolds.

    Args:
        analysis: Repository analysis data

    Returns:
        List of task metadata dicts with keys: task_id, task_type, target_file
    """
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

    available_tasks: list[dict[str, str]] = []
    existing_ids: set[str] = set()

    for task_type in ["assertion", "coverage", "sequence"]:
        candidates = type_to_candidates.get(task_type, [])
        for candidate in candidates:
            slug_base = slugify(Path(candidate).stem)
            slug = f"{task_type}-{slug_base}"

            # Handle duplicate task IDs
            counter = 1
            task_id = slug
            while task_id in existing_ids:
                counter += 1
                task_id = f"{slug}-{counter}"

            existing_ids.add(task_id)
            available_tasks.append({
                "task_id": task_id,
                "task_type": task_type,
                "target_file": candidate,
            })

    return available_tasks


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


async def _run_agent_with_claude(scaffold: TaskScaffold, logger, status_cb=None) -> dict[str, Any]:
    """Run Claude agent to generate a complete terminal-bench task.

    Args:
        scaffold: Task scaffold to build
        logger: Logger instance
        status_cb: Optional status callback for live feed
    """
    from ..core.ai_structured import query_with_pydantic_response

    logger.debug(f"Starting agent for task: {scaffold.task_id}")

    prompt = _agent_prompt_for_scaffold(scaffold)
    system_prompt = (
        "You are an expert Terminal-Bench task builder and DV (Design Verification) engineer. "
        "You create clear, well-tested tasks for evaluating AI agents' verification skills. "
        "Work only within the current working directory (cwd). "
        "Use the Bash tool for `tb tasks check` quality validation and `tb tasks build` for Docker builds. "
        "No network access. No package installation. "
        "Iterate using `tb tasks check` until quality checks pass or you determine the task cannot be completed. "
        "Pay close attention to quality check failures and fix instruction clarity and test alignment issues."
    )

    try:
        result = await query_with_pydantic_response(
            prompt=prompt,
            response_model=TBAgentResult,
            system_prompt=system_prompt,
            cwd=str(scaffold.path),
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", "create_file", "edit_file"],
            status_cb=status_cb,
        )

        logger.debug(
            f"Agent completed for {scaffold.task_id}: "
            f"status={result.status}, tb_check_passed={result.tb_check_passed}"
        )

        return result.model_dump()

    except Exception as exc:
        logger.warning(f"Agent failed for {scaffold.task_id}: {exc}")
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


@flow(name="Build Terminal-Bench Tasks", validate_parameters=False)
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
    logger.debug("Prepared %d task scaffolds", len(plans))

    # Run Claude agents to generate task content
    agent_results: list[dict[str, Any]] = []
    if len(plans) > 0:
        console = Console()
        
        # For single agent, show more detailed progress; for multiple, show progress bar
        if agent_concurrency == 1 and len(plans) == 1:
            # Single agent - show minimal status
            console.print(f"[cyan]Running Claude agent for task: {plans[0].task_id}[/cyan]")
            console.print("[dim]This may take several minutes...[/dim]\n")
            result = await _run_agent_with_claude(plans[0], logger)
            agent_results = [result]

            # Show summary after completion
            if result.get("status") == "ok":
                console.print(f"[green]✓[/green] Task {plans[0].task_id} generated successfully")
            else:
                console.print(f"[yellow]⚠[/yellow] Task {plans[0].task_id} had issues")
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

        logger.debug("Agent stage complete")

    validation_results: list[dict[str, Any]] = []
    if run_validation:
        semaphore = asyncio.Semaphore(2)

        async def validate_single(scaffold: TaskScaffold) -> dict[str, Any]:
            async with semaphore:
                result = await _run_tb_check(scaffold.path)
                result["task_id"] = scaffold.task_id
                return result

        validation_results = await asyncio.gather(*(validate_single(plan) for plan in plans))
        logger.debug("Validation stage complete")

    summary_path = output_dir / "build_summary.json"
    summary = {
        "analysis": analysis_data,
        "agent_results": agent_results,
        "validation_results": validation_results,
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    return summary


@flow(name="Build Single Terminal-Bench Task", validate_parameters=False)
async def build_single_terminal_bench_task(
    analysis_data: dict,
    task_id: str,
    output_dir: str,
    run_validation: bool = True,
    console: Console | None = None,
) -> dict:
    """Build a single terminal-bench task (simplified flow).

    Args:
        analysis_data: Repository analysis dictionary
        task_id: Specific task ID to build
        output_dir: Output directory for task
        run_validation: Whether to run tb check validation
        console: Optional Rich console for output

    Returns:
        Dictionary with task generation results
    """
    try:
        logger = get_run_logger()
    except MissingContextError:
        logger = logging.getLogger("dvsmith.terminal_bench_flow")

    analysis = RepoAnalysis.from_dict(analysis_data)
    if not analysis.repo_root:
        raise ValueError("RepoAnalysis.repo_root is required")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Verify task_id exists
    available_tasks = preview_available_tasks(analysis)
    task_info = next((t for t in available_tasks if t["task_id"] == task_id), None)

    if not task_info:
        available_ids = [t["task_id"] for t in available_tasks]
        raise ValueError(
            f"Task ID '{task_id}' not found. Available tasks: {', '.join(available_ids)}"
        )

    logger.debug(f"Building task: {task_id} ({task_info['task_type']}) -> {task_info['target_file']}")

    # Create single scaffold
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

    scaffold = scaffolder.create_scaffold(
        task_id=task_id,
        task_type=task_info["task_type"],
        target=task_info["target_file"],
    )

    logger.debug(f"Scaffold created at: {scaffold.path}")

    # Run Claude agent with status updates
    if console is None:
        console = Console()
    console.print(f"[cyan]Generating task: {task_id}[/cyan]")
    console.print(f"[dim]Type: {task_info['task_type']} | Target: {task_info['target_file']}[/dim]")
    console.print()

    # Create simple callback that prints each status update
    def status_callback(msg: str):
        console.print(f"  [dim]{msg}[/dim]")

    agent_result = await _run_agent_with_claude(
        scaffold=scaffold,
        logger=logger,
        status_cb=status_callback,
    )

    # Show completion status
    if agent_result.get("status") == "ok":
        console.print(f"\n[green]✓[/green] Task generated successfully")
    else:
        console.print(f"\n[yellow]⚠[/yellow] Task had issues: {agent_result.get('notes', 'Unknown')}")

    # Run validation if requested
    validation_result = None
    if run_validation:
        validation_result = await _run_tb_check(scaffold.path)
        validation_result["task_id"] = task_id

    # Save summary
    summary = {
        "task_id": task_id,
        "task_type": task_info["task_type"],
        "target_file": task_info["target_file"],
        "agent_result": agent_result,
        "validation_result": validation_result,
    }

    summary_path = output_dir / task_id / "build_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    return summary


__all__ = ["build_terminal_bench_tasks", "build_single_terminal_bench_task", "preview_available_tasks"]
