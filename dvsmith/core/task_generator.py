"""Task generator - converts original tests into task specifications."""

import asyncio
import contextlib
import json
import re
from pathlib import Path
from typing import Any, Optional

from tqdm import tqdm

from ..config import get_logger
from .ai_structured import query_with_pydantic_response
from .ai_models import CompleteTaskMetadata

logger = get_logger(__name__)
from .models import (
    AcceptanceCriteria,
    RepoAnalysis,
    Simulator,
    TaskCategory,
    TaskLevel,
    TaskSpec,
    UVMTest,
)


class TaskGenerator:
    """Generate task specifications from analyzed tests."""

    def __init__(self, repo_analysis: RepoAnalysis, profile_config: dict[str, Any]) -> None:
        """Initialize task generator.

        Args:
            repo_analysis: Analysis results from AI analyzer
            profile_config: Profile configuration (for grading/thresholds)
        """
        self.analysis = repo_analysis
        self.config = profile_config
        self.backup_dir = Path("backups/original_tests")
        self.cwd = str(Path.cwd())

    def generate_tasks(
        self, output_dir: Path, smoke_tests: Optional[list[str]] = None
    ) -> list[TaskSpec]:
        """Generate task specifications for all tests (backward compatible).

        Args:
            output_dir: Directory to write task markdown files
            smoke_tests: Tests to exclude (kept as smoke tests)

        Returns:
            List of generated TaskSpec objects
        """
        return asyncio.run(self.generate_tasks_async(output_dir, smoke_tests))

    async def generate_tasks_async(
        self, output_dir: Path, smoke_tests: Optional[list[str]] = None, status_cb=None
    ) -> list[TaskSpec]:
        """Generate task specifications for all tests in parallel.

        Args:
            output_dir: Directory to write task markdown files
            smoke_tests: Tests to exclude (kept as smoke tests)

        Returns:
            List of generated TaskSpec objects
        """
        output_dir.mkdir(exist_ok=True, parents=True)
        smoke_tests = smoke_tests or []

        # Collect tests to generate tasks for
        tests_to_generate = []
        for test in self.analysis.tests:
            # Skip smoke tests
            if test.name in smoke_tests:
                continue
            # Skip base classes
            if "base" in test.name.lower():
                continue
            tests_to_generate.append(test)

        if not tests_to_generate:
            logger.info("No tasks to generate")
            return []

        logger.info(f"Generating {len(tests_to_generate)} tasks in parallel...")

        # Generate all tasks in parallel (with batching for rate limiting)
        BATCH_SIZE = 5  # Max concurrent AI calls
        all_tasks = []

        total_batches = (len(tests_to_generate) + BATCH_SIZE - 1) // BATCH_SIZE
        with tqdm(total=len(tests_to_generate), desc="Generating tasks", unit="task") as pbar:
            for batch_start in range(0, len(tests_to_generate), BATCH_SIZE):
                batch = tests_to_generate[batch_start : batch_start + BATCH_SIZE]

                # Generate tasks in parallel for this batch
                batch_tasks = await asyncio.gather(
                    *[
                        self._create_task_for_test_async(test, batch_start + i + 1)
                        for i, test in enumerate(batch)
                    ]
                )

                all_tasks.extend(batch_tasks)
                pbar.update(len(batch))

        # Write all task files
        for task_id, task in enumerate(all_tasks, 1):
            task_file = output_dir / f"task_{task_id:03d}_{task.id}.md"
            task_file.write_text(task.to_markdown())
            logger.info(f"Generated: {task_file.name}")

        logger.info(f"Generated {len(all_tasks)} tasks")
        return all_tasks

    def _create_task_for_test(self, test: UVMTest, task_id: int) -> TaskSpec:
        """Create a task specification for a UVM test.

        Args:
            test: UVM test to convert
            task_id: Numeric task ID

        Returns:
            TaskSpec
        """
        return asyncio.run(self._create_task_for_test_async(test, task_id))

    async def _create_task_for_test_async(self, test: UVMTest, task_id: int) -> TaskSpec:
        """Create a task specification for a UVM test (async).

        Args:
            test: UVM test to convert
            task_id: Numeric task ID

        Returns:
            TaskSpec
        """
        # Generate ALL task metadata in a single AI call
        metadata = await self._generate_complete_metadata_async(test)

        # Parse difficulty from metadata
        difficulty = metadata.difficulty.strip().upper()
        if "EASY" in difficulty:
            level = TaskLevel.EASY
        elif "HARD" in difficulty:
            level = TaskLevel.HARD
        else:
            level = TaskLevel.MEDIUM

        # Create acceptance criteria with AI-inferred covergroups
        acceptance = self._create_acceptance_criteria_with_covergroups(test, metadata.covergroups)

        # Get supported simulators from profile
        supported_sims = self._get_supported_simulators()

        # Create task spec
        # Sanitize task name for use in IDs and filenames
        sanitized_id = (
            metadata.task_name.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
        )
        task = TaskSpec(
            id=sanitized_id,
            name=metadata.task_name,
            level=level,
            bench_name=self.config.get("name", "unknown"),
            description=metadata.description,
            goal=metadata.goal,
            acceptance=acceptance,
            hints=metadata.hints,
            original_test_files=[test.file_path],
            supported_simulators=supported_sims,
            notes=self._generate_notes(test),
        )

        return task

    def _generate_complete_metadata(self, test: UVMTest) -> CompleteTaskMetadata:
        """Generate all task metadata in a single AI call.

        Args:
            test: UVM test

        Returns:
            CompleteTaskMetadata with all fields populated
        """
        return asyncio.run(self._generate_complete_metadata_async(test))

    async def _generate_complete_metadata_async(self, test: UVMTest) -> CompleteTaskMetadata:
        """Generate all task metadata in a single AI call (async).

        Args:
            test: UVM test

        Returns:
            CompleteTaskMetadata with all fields populated
        """
        # Read test code
        test_code = ""
        if test.file_path.exists():
            with contextlib.suppress(Exception):
                test_code = test.file_path.read_text()[:3000]

        # Get available covergroups (already strings in analysis.coverage_components)
        available_cgs = self.analysis.coverage_components if self.analysis.coverage_components else []
        if not available_cgs:
            available_cgs = (
                self.config.get("coverage", {}).get("questa", {}).get("functional_covergroups", [])
            )

        covergroups_info = f"""
Available covergroups in the testbench:
{json.dumps(available_cgs, indent=2)}

Select 2-4 of the most relevant covergroups that this test should target.
If none are clearly relevant, select the most general covergroups.
"""

        prompt = f"""Analyze this UVM test and generate complete task metadata for a verification challenge (similar to LeetCode for hardware).

**Test Information:**
- Test name: {test.name}
- Base class: {test.base_class}
- Test description: {test.description or 'Not available'}

**Test file snippet:**
```systemverilog
{test_code}
```

{covergroups_info if available_cgs else "No covergroups available."}

**Generate the following:**

1. **task_name**: Human-readable name (2-5 words, clear and professional)
   - Examples: "Sparse Write Test", "Concurrent Read/Write Test", "Back-to-Back Transfers"

2. **difficulty**: Classify as EASY, MEDIUM, or HARD
   - EASY: Simple, straightforward tests (basic reads/writes, single transactions)
   - MEDIUM: Moderate complexity (some randomization, basic sequences, simple scenarios)
   - HARD: Complex tests (advanced randomization, concurrent operations, complex protocols)

3. **description**: Clear, detailed task description (2-4 sentences)
   - Explain what functionality needs to be tested
   - Describe key verification objectives
   - Mention important protocol details or behaviors
   - Sound natural and human-written (not templated)
   - Do NOT include implementation details - focus on WHAT needs to be verified

4. **goal**: Concise goal statement (1-2 sentences)
   - Mention writing UVM test(s) and/or sequence(s)
   - Reference achieving coverage targets
   - State the specific scenario being tested

5. **hints**: List of 3-5 helpful hints that guide WITHOUT giving away the solution
   - Which sequences to use or create
   - Configuration parameters to set
   - Key protocol features to exercise
   - Randomization strategies
   - Coverage targets to focus on

6. **covergroups**: List of 2-4 relevant covergroup names from the available list
   - Select covergroups most relevant to this test
   - If none are clearly relevant, select the most general ones

Analyze the test thoroughly and provide comprehensive, high-quality metadata.
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=CompleteTaskMetadata,
                system_prompt="You are an expert verification engineer creating high-quality task specifications. Be thorough, specific, and professional.",
                cwd=str(self.cwd),
            )
            return result

        except Exception as e:
            raise RuntimeError(f"AI task metadata generation failed: {e}") from e

    def _create_acceptance_criteria_with_covergroups(
        self, test: UVMTest, covergroups: list[str]
    ) -> AcceptanceCriteria:
        """Create acceptance criteria for a test with pre-selected covergroups.

        Args:
            test: UVM test
            covergroups: List of covergroup names selected by AI

        Returns:
            AcceptanceCriteria
        """
        grading_config = self.config.get("grading", {})
        thresholds = grading_config.get("thresholds", {})
        weights = grading_config.get("weights", {})

        # Validate covergroups exist (already strings in analysis.coverage_components)
        available_cgs = self.analysis.coverage_components if self.analysis.coverage_components else []
        if not available_cgs:
            available_cgs = (
                self.config.get("coverage", {}).get("questa", {}).get("functional_covergroups", [])
            )

        # Filter to only valid covergroups
        target_bins = [cg for cg in covergroups if cg in available_cgs]
        if not target_bins and available_cgs:
            target_bins = available_cgs[:3]

        criteria = AcceptanceCriteria(
            functional_bins=target_bins,
            functional_min_pct=thresholds.get("functional", {}).get("min_pct", 80.0),
            functional_strategy=thresholds.get("functional", {}).get("strategy", "any_of"),
            code_statements_min_pct=thresholds.get("code", {}).get("statements_min_pct", 70.0),
            code_branches_min_pct=thresholds.get("code", {}).get("branches_min_pct", 60.0),
            code_toggles_min_pct=thresholds.get("code", {}).get("toggles_min_pct", 50.0),
            max_scoreboard_errors=thresholds.get("health", {}).get("max_scoreboard_errors", 0),
            max_uvm_errors=thresholds.get("health", {}).get("max_uvm_errors", 0),
            max_uvm_fatals=thresholds.get("health", {}).get("max_uvm_fatals", 0),
            all_assertions_pass=thresholds.get("health", {}).get("all_assertions_pass", True),
            weights={
                "functional_coverage": weights.get("functional_coverage", 0.6),
                "code_coverage": weights.get("code_coverage", 0.3),
                "health": weights.get("health", 0.1),
            },
        )

        return criteria

    def _create_acceptance_criteria(self, test: UVMTest) -> AcceptanceCriteria:
        """Create acceptance criteria for a test.

        Uses profile config for default thresholds, but can be refined
        based on test characteristics.
        """
        grading_config = self.config.get("grading", {})
        thresholds = grading_config.get("thresholds", {})
        weights = grading_config.get("weights", {})

        # Find relevant covergroups for this test
        # Heuristic: match covergroup names to test name patterns
        target_bins = self._infer_target_covergroups(test)

        criteria = AcceptanceCriteria(
            functional_bins=target_bins,
            functional_min_pct=thresholds.get("functional", {}).get("min_pct", 80.0),
            functional_strategy=thresholds.get("functional", {}).get("strategy", "any_of"),
            code_statements_min_pct=thresholds.get("code", {}).get("statements_min_pct", 70.0),
            code_branches_min_pct=thresholds.get("code", {}).get("branches_min_pct", 60.0),
            code_toggles_min_pct=thresholds.get("code", {}).get("toggles_min_pct", 50.0),
            max_scoreboard_errors=thresholds.get("health", {}).get("max_scoreboard_errors", 0),
            max_uvm_errors=thresholds.get("health", {}).get("max_uvm_errors", 0),
            max_uvm_fatals=thresholds.get("health", {}).get("max_uvm_fatals", 0),
            all_assertions_pass=thresholds.get("health", {}).get("all_assertions_pass", True),
            weights={
                "functional_coverage": weights.get("functional_coverage", 0.6),
                "code_coverage": weights.get("code_coverage", 0.3),
                "health": weights.get("health", 0.1),
            },
        )

        return criteria

    def _generate_notes(self, test: UVMTest) -> Optional[str]:
        """Generate additional notes about the task.

        Args:
            test: UVM test

        Returns:
            Notes string or None
        """
        notes = []

        # Add information about original test location
        notes.append(f"Original test: `{test.file_path}`")

        # Add information about base class
        notes.append(f"Base class: `{test.base_class}`")

        if notes:
            return "\n".join(notes)

        return None

    def _get_supported_simulators(self) -> list[Simulator]:
        """Get list of supported simulators from profile.

        Returns:
            List of Simulator enums
        """
        sim_names = self.config.get("simulators", [])
        simulators = []

        for name in sim_names:
            try:
                sim = Simulator(name)
                simulators.append(sim)
            except ValueError:
                logger.warning(f"Unknown simulator '{name}'")

        return simulators
