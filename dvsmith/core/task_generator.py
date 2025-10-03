"""Task generator - converts original tests into task specifications."""

import asyncio
import contextlib
import json
import re
from pathlib import Path
from typing import Any, Optional

from .ai_structured import query_with_pydantic_response
from .ai_models import (
    TaskName,
    TaskDifficulty,
    TaskDescription,
    TaskGoal,
    TaskHints,
    CovergroupSelection,
)
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

    def generate_tasks(self, output_dir: Path,
                      smoke_tests: Optional[list[str]] = None) -> list[TaskSpec]:
        """Generate task specifications for all tests (backward compatible).

        Args:
            output_dir: Directory to write task markdown files
            smoke_tests: Tests to exclude (kept as smoke tests)

        Returns:
            List of generated TaskSpec objects
        """
        # Backward compatible: generate only STIMULUS tasks
        return self.generate_tasks_multi(
            output_dir=output_dir,
            modes=[TaskCategory.STIMULUS],
            smoke_tests=smoke_tests
        )

    def generate_tasks_multi(
        self,
        output_dir: Path,
        modes: list[TaskCategory],
        smoke_tests: Optional[list[str]] = None,
        max_coverage_tasks: int = 12
    ) -> list[TaskSpec]:
        """Generate tasks across multiple categories.

        Args:
            output_dir: Directory to write task markdown files
            modes: List of TaskCategory to generate
            smoke_tests: Tests to exclude for stimulus tasks
            max_coverage_tasks: Limit on number of coverage tasks

        Returns:
            List of generated TaskSpec objects
        """
        output_dir.mkdir(exist_ok=True, parents=True)
        smoke_tests = smoke_tests or []

        tasks: list[TaskSpec] = []
        seq = 1

        # Stimulus / Test creation
        if TaskCategory.STIMULUS in modes:
            for test in self.analysis.tests:
                if test.name in smoke_tests:
                    continue
                if "base" in test.name.lower():
                    continue
                task = self._create_task_for_test(test, seq)
                task.category = TaskCategory.STIMULUS
                tasks.append(task)
                task_file = output_dir / f"task_{seq:03d}_{self._slug(task.id)}.md"
                task_file.write_text(task.to_markdown())
                print(f"[TaskGen] Generated: {task_file.name}")
                seq += 1

        # Functional coverage closure tasks
        if TaskCategory.COVERAGE_FUNC in modes:
            cov_tasks = self._generate_functional_coverage_tasks(max_coverage_tasks)
            for t in cov_tasks:
                t.category = TaskCategory.COVERAGE_FUNC
                task_file = output_dir / f"task_{seq:03d}_{self._slug(t.id)}.md"
                task_file.write_text(t.to_markdown())
                tasks.append(t)
                print(f"[TaskGen] Generated: {task_file.name}")
                seq += 1

        print(f"[TaskGen] Generated {len(tasks)} tasks across categories: {', '.join(m.value for m in modes)}")
        return tasks

    def _create_task_for_test(self, test: UVMTest, task_id: int) -> TaskSpec:
        """Create a task specification for a UVM test.

        Args:
            test: UVM test to convert
            task_id: Numeric task ID

        Returns:
            TaskSpec
        """
        # Generate task name using AI
        task_name = self._generate_task_name_with_ai(test)

        # Infer difficulty using AI
        level = self._infer_difficulty_with_ai(test)

        # Create acceptance criteria with AI-inferred covergroups
        acceptance = self._create_acceptance_criteria(test)

        # Extract hints from test description/name
        hints = self._extract_hints_with_ai(test)

        # Get supported simulators from profile
        supported_sims = self._get_supported_simulators()

        # Create task spec
        # Sanitize task name for use in IDs and filenames
        task_slug = task_name.lower().replace(' ', '_').replace('/', '_').replace('\\', '_')
        task = TaskSpec(
            id=task_slug,
            name=task_name,
            level=level,
            bench_name=self.config.get("name", "unknown"),
            description=self._generate_description_with_ai(test),
            goal=self._generate_goal_with_ai(test),
            acceptance=acceptance,
            hints=hints,
            original_test_files=[test.file_path],
            supported_simulators=supported_sims,
            notes=self._generate_notes(test)
        )

        return task


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
                "health": weights.get("health", 0.1)
            }
        )

        return criteria

    def _infer_target_covergroups(self, test: UVMTest) -> list[str]:
        """Infer which covergroups are relevant for a test using AI."""
        return asyncio.run(self._infer_target_covergroups_async(test))

    async def _infer_target_covergroups_async(self, test: UVMTest) -> list[str]:
        """Infer which covergroups are relevant for a test using AI (async)."""
        available_cgs = self.analysis.covergroups

        if not available_cgs:
            profile_cgs = self.config.get("coverage", {}).get("questa", {}).get(
                "functional_covergroups", [])
            return profile_cgs[:3] if profile_cgs else []

        test_code = ""
        if test.file_path.exists():
            with contextlib.suppress(Exception):
                test_code = test.file_path.read_text()[:2000]

        prompt = f"""Analyze this UVM test to determine which functional coverage groups should be targeted.

Test name: {test.name}
Test description: {test.description or 'Not available'}

Test file snippet:
```systemverilog
{test_code}
```

Available covergroups in the testbench:
{json.dumps(available_cgs, indent=2)}

Select 2-4 of the most relevant covergroups from the available list that this test should target.
If none are clearly relevant, select the most general covergroups.
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=CovergroupSelection,
                system_prompt="You are an expert verification engineer analyzing test coverage requirements.",
                cwd=self.cwd
            )

            # Filter to only include covergroups that exist
            valid_targets = [t for t in result.covergroups if t in available_cgs]
            return valid_targets if valid_targets else available_cgs[:3]

        except Exception as e:
            print(f"[TaskGen] Warning: AI covergroup inference failed for {test.name}: {e}")
            return available_cgs[:3]


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
                print(f"[TaskGen] Warning: Unknown simulator '{name}'")

        return simulators

    # AI-powered generation methods

    def _generate_task_name_with_ai(self, test: UVMTest) -> str:
        """Generate human-readable task name using AI.

        Args:
            test: UVM test

        Returns:
            Task name string
        """
        return asyncio.run(self._generate_task_name_with_ai_async(test))

    async def _generate_task_name_with_ai_async(self, test: UVMTest) -> str:
        """Generate human-readable task name using AI (async).

        Args:
            test: UVM test

        Returns:
            Task name string
        """
        prompt = f"""Generate a concise, human-readable task name for this UVM verification test.

Test class name: {test.name}
Test description: {test.description or 'Not available'}

The name should be 2-5 words, clear and professional.

Examples:
- "apb_master_sparse_write_test" -> "Sparse Write Test"
- "axi_concurrent_read_write_test" -> "Concurrent Read/Write Test"
- "i3c_back_to_back_transfers_test" -> "Back-to-Back Transfers"
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=TaskName,
                system_prompt="You are an expert verification engineer creating clear, concise task names.",
                cwd=self.cwd
            )
            return result.name.strip()

        except Exception as e:
            # Fallback to simple transformation
            print(f"[TaskGen] Warning: AI task name generation failed for {test.name}: {e}")
            name = test.name.replace("_test", "").replace("_seq", "")
            words = name.split("_")
            return " ".join(w.capitalize() for w in words)

    def _infer_difficulty_with_ai(self, test: UVMTest) -> TaskLevel:
        """Infer task difficulty using AI."""
        return asyncio.run(self._infer_difficulty_with_ai_async(test))

    async def _infer_difficulty_with_ai_async(self, test: UVMTest) -> TaskLevel:
        """Infer task difficulty using AI (async)."""
        test_code = ""
        if test.file_path.exists():
            with contextlib.suppress(Exception):
                test_code = test.file_path.read_text()[:2000]

        prompt = f"""Analyze this UVM test to determine its difficulty level.

Test name: {test.name}
Base class: {test.base_class}
Test description: {test.description or 'Not available'}

Test file snippet:
```systemverilog
{test_code}
```

Classify the difficulty:
- EASY: Simple, straightforward tests (basic reads/writes, single transactions)
- MEDIUM: Moderate complexity (some randomization, basic sequences, simple scenarios)
- HARD: Complex tests (advanced randomization, concurrent operations, complex protocols, stress testing)
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=TaskDifficulty,
                system_prompt="You are an expert verification engineer assessing test complexity.",
                cwd=self.cwd
            )

            difficulty = result.difficulty.strip().upper()
            if "EASY" in difficulty:
                return TaskLevel.EASY
            elif "HARD" in difficulty:
                return TaskLevel.HARD
            else:
                return TaskLevel.MEDIUM

        except Exception as e:
            print(f"[TaskGen] Warning: AI difficulty inference failed for {test.name}: {e}")
            return TaskLevel.MEDIUM

    def _generate_description_with_ai(self, test: UVMTest) -> str:
        """Generate thorough task description using AI."""
        return asyncio.run(self._generate_description_with_ai_async(test))

    async def _generate_description_with_ai_async(self, test: UVMTest) -> str:
        """Generate thorough task description using AI (async)."""
        test_code = ""
        if test.file_path.exists():
            with contextlib.suppress(Exception):
                test_code = test.file_path.read_text()[:3000]

        prompt = f"""Create a task specification for a UVM verification challenge (similar to LeetCode for hardware).

Test name: {test.name}
Base class: {test.base_class}
Test description: {test.description or 'Not available'}

Test file snippet:
```systemverilog
{test_code}
```

Write a clear, detailed task description (2-4 sentences) that:
1. Explains what functionality needs to be tested
2. Describes the key verification objectives
3. Mentions important protocol details or behaviors to exercise
4. Sounds natural and human-written (not templated)

Do NOT include implementation details like "write a UVM test" - focus on WHAT needs to be verified.
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=TaskDescription,
                system_prompt="You are an expert verification engineer writing task specifications. Be thorough and specific.",
                cwd=self.cwd
            )
            return result.description.strip()

        except Exception as e:
            raise RuntimeError(f"AI description generation failed: {e}") from e

    def _generate_goal_with_ai(self, test: UVMTest) -> str:
        """Generate task goal using AI."""
        return asyncio.run(self._generate_goal_with_ai_async(test))

    async def _generate_goal_with_ai_async(self, test: UVMTest) -> str:
        """Generate task goal using AI (async)."""
        prompt = f"""Create a task goal for a UVM verification challenge.

Test name: {test.name}
Test description: {test.description or 'Not available'}

Write a concise goal statement (1-2 sentences) that tells what needs to be accomplished.
The goal should mention:
- Writing UVM test(s) and/or sequence(s)
- Achieving coverage targets
- The specific scenario being tested

Keep it actionable and clear.
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=TaskGoal,
                system_prompt="You are an expert verification engineer. Write clear, actionable goals.",
                cwd=self.cwd
            )
            return result.goal.strip()

        except Exception as e:
            raise RuntimeError(f"AI goal generation failed: {e}") from e

    def _extract_hints_with_ai(self, test: UVMTest) -> list[str]:
        """Extract helpful hints using AI."""
        return asyncio.run(self._extract_hints_with_ai_async(test))

    async def _extract_hints_with_ai_async(self, test: UVMTest) -> list[str]:
        """Extract helpful hints using AI (async)."""
        test_code = ""
        if test.file_path.exists():
            with contextlib.suppress(Exception):
                test_code = test.file_path.read_text()[:3000]

        prompt = f"""Create hints for a UVM verification challenge.

Test name: {test.name}
Base class: {test.base_class}
Test description: {test.description or 'Not available'}

Test file snippet:
```systemverilog
{test_code}
```

Generate 3-5 helpful hints that guide WITHOUT giving away the solution.
Hints should mention:
- Which sequences to use or create
- Configuration parameters to set
- Key protocol features to exercise
- Testing strategies or patterns
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=TaskHints,
                system_prompt="You are an expert verification engineer. Provide helpful but not overly explicit hints.",
                cwd=self.cwd
            )
            return result.hints

        except Exception as e:
            print(f"[TaskGen] Warning: Hints generation failed for {test.name}: {e}")
            return []

    def _generate_functional_coverage_tasks(self, max_tasks: int) -> list[TaskSpec]:
        """Create functional coverage tasks from discovered or configured covergroups."""
        groups: list[str] = []

        # Prefer discovered covergroups
        if self.analysis.covergroups:
            groups = list(dict.fromkeys(self.analysis.covergroups))  # preserve order, dedup
        else:
            # Fallback to profile config if available
            groups = self._configured_covergroups()

        if not groups:
            print("[TaskGen] No covergroups discovered or configured; skipping coverage tasks")
            return []

        # Limit number of tasks
        groups = groups[:max_tasks]

        # Pull thresholds/weights
        grading = self.config.get("grading", {})
        thresholds = grading.get("thresholds", {})
        func_cfg = thresholds.get("functional", {})
        min_pct = float(func_cfg.get("min_pct", 80.0))
        strategy = func_cfg.get("strategy", "any_of")
        weights_cfg = grading.get("weights", {})

        supported_sims = self._get_supported_simulators()

        tasks: list[TaskSpec] = []
        for g in groups:
            display = g
            slug = self._slug(f"cov_{g}")
            name = f"Functional Coverage: {display}"
            description = (
                f"Increase functional coverage for the covergroup `{display}` by creating or adapting "
                f"stimulus and sequences that exercise its key scenarios. Focus on meaningful variation "
                f"and corner-cases relevant to the protocol."
            )
            goal = (
                f"Achieve at least {min_pct:.0f}% coverage in `{display}` while keeping the testbench healthy "
                f"(no UVM errors/fatals or scoreboard errors)."
            )

            acceptance = AcceptanceCriteria(
                functional_bins=[display],
                functional_min_pct=min_pct,
                functional_strategy=strategy,
                code_statements_min_pct=thresholds.get("code", {}).get("statements_min_pct", 70.0),
                code_branches_min_pct=thresholds.get("code", {}).get("branches_min_pct", 60.0),
                code_toggles_min_pct=thresholds.get("code", {}).get("toggles_min_pct", 50.0),
                max_scoreboard_errors=thresholds.get("health", {}).get("max_scoreboard_errors", 0),
                max_uvm_errors=thresholds.get("health", {}).get("max_uvm_errors", 0),
                max_uvm_fatals=thresholds.get("health", {}).get("max_uvm_fatals", 0),
                all_assertions_pass=thresholds.get("health", {}).get("all_assertions_pass", True),
                weights={
                    "functional_coverage": weights_cfg.get("functional_coverage", 0.6),
                    "code_coverage": weights_cfg.get("code_coverage", 0.3),
                    "health": weights_cfg.get("health", 0.1)
                }
            )

            task = TaskSpec(
                id=slug,
                name=name,
                level=TaskLevel.MEDIUM,  # default; could be inferred later
                bench_name=self.config.get("name", "unknown"),
                description=description,
                goal=goal,
                acceptance=acceptance,
                category=TaskCategory.COVERAGE_FUNC,
                hints=[
                    "Use constrained-random sequences to explore corner cases.",
                    "Tweak sequence configuration knobs (burst types, alignment, lengths, inter-packet gaps).",
                    "Leverage virtual sequences to orchestrate concurrent traffic if applicable.",
                ],
                original_test_files=[],  # no single 'original' test maps to a coverage group
                supported_simulators=supported_sims,
                notes=None
            )
            tasks.append(task)

        return tasks

    def _configured_covergroups(self) -> list[str]:
        """Read covergroups from profile config for fallback coverage tasks."""
        cov = self.config.get("coverage", {})
        # First check a simulator-scoped section, then a generic key.
        groups = []
        for key in ("questa", "xcelium", "vcs"):
            groups = cov.get(key, {}).get("functional_covergroups", [])
            if groups:
                break
        if not groups:
            groups = cov.get("functional_covergroups", [])
        return list(groups) if isinstance(groups, list) else []

    def _slug(self, text: str) -> str:
        """Normalize a string for safe IDs/filenames."""
        slug = text.lower()
        slug = slug.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(".", "_")
        slug = re.sub(r"[^a-z0-9_\.-]", "", slug)
        return slug.strip("._")