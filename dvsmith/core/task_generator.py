"""Task generator - converts original tests into task specifications."""

import contextlib
import json
import os
from pathlib import Path
from typing import Any, Optional

from anthropic import Anthropic

from .models import (
    AcceptanceCriteria,
    RepoAnalysis,
    Simulator,
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

        # Initialize Anthropic client (required)
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.client = Anthropic(api_key=api_key)
        print("[TaskGen] Using Claude for task descriptions")

    def generate_tasks(self, output_dir: Path,
                      smoke_tests: Optional[list[str]] = None) -> list[TaskSpec]:
        """Generate task specifications for all tests.

        Args:
            output_dir: Directory to write task markdown files
            smoke_tests: Tests to exclude (kept as smoke tests)

        Returns:
            List of generated TaskSpec objects
        """
        output_dir.mkdir(exist_ok=True, parents=True)
        smoke_tests = smoke_tests or []

        tasks = []
        task_id = 1

        for test in self.analysis.tests:
            # Skip smoke tests
            if test.name in smoke_tests:
                continue

            # Skip base classes
            if "base" in test.name.lower():
                continue

            # Generate task spec
            task = self._create_task_for_test(test, task_id)
            tasks.append(task)

            # Write markdown file
            task_file = output_dir / f"task_{task_id:03d}_{task.id}.md"
            task_file.write_text(task.to_markdown())

            print(f"[TaskGen] Generated: {task_file.name}")

            task_id += 1

        print(f"[TaskGen] Generated {len(tasks)} tasks")
        return tasks

    def _create_task_for_test(self, test: UVMTest, task_id: int) -> TaskSpec:
        """Create a task specification for a UVM test.

        Args:
            test: UVM test to convert
            task_id: Numeric task ID

        Returns:
            TaskSpec
        """
        # Infer task name and level
        task_name = self._derive_task_name(test.name)
        level = self._infer_difficulty(test)

        # Create acceptance criteria based on test
        acceptance = self._create_acceptance_criteria(test)

        # Extract hints from test description/name
        hints = self._extract_hints(test)

        # Get supported simulators from profile
        supported_sims = self._get_supported_simulators()

        # Create task spec
        task = TaskSpec(
            id=f"{task_name.lower().replace(' ', '_')}",
            name=task_name,
            level=level,
            bench_name=self.config.get("name", "unknown"),
            description=self._generate_description(test),
            goal=self._generate_goal(test),
            acceptance=acceptance,
            hints=hints,
            original_test_files=[test.file_path],
            supported_simulators=supported_sims,
            notes=self._generate_notes(test)
        )

        return task

    def _derive_task_name(self, test_name: str) -> str:
        """Derive human-readable task name from test class name.

        Example:
            apb_master_sparse_write_test -> APB Sparse Write Test
        """
        # Remove common suffixes
        name = test_name.replace("_test", "").replace("_seq", "")

        # Remove common prefixes
        for prefix in ["apb_", "axi_", "i3c_", "spi_", "master_", "slave_"]:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break

        # Convert to title case
        words = name.split("_")
        return " ".join(w.capitalize() for w in words)

    def _infer_difficulty(self, test: UVMTest) -> TaskLevel:
        """Infer task difficulty from test characteristics.

        Heuristics:
        - Simple read/write tests -> EASY
        - Tests with constraints, randomization -> MEDIUM
        - Tests with complex scenarios, multiple sequences -> HARD
        """
        name_lower = test.name.lower()

        # Easy indicators
        easy_keywords = ["simple", "basic", "smoke", "sanity", "single"]
        if any(kw in name_lower for kw in easy_keywords):
            return TaskLevel.EASY

        # Hard indicators
        hard_keywords = ["complex", "concurrent", "stress", "random",
                        "outstanding", "interleave", "ooo"]
        if any(kw in name_lower for kw in hard_keywords):
            return TaskLevel.HARD

        # Default to medium
        return TaskLevel.MEDIUM

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
        """Infer which covergroups are relevant for a test.

        Uses keyword matching between test name and covergroup names.
        """
        targets = []

        # Extract keywords from test name
        test_keywords = set(test.name.lower().replace("_test", "").split("_"))

        # Match against known covergroups
        for cg in self.analysis.covergroups:
            cg_lower = cg.lower()

            # Check if any test keyword appears in covergroup name
            for keyword in test_keywords:
                if len(keyword) > 3 and keyword in cg_lower:
                    targets.append(cg)
                    break

        # If no matches, include common master/slave coverage groups
        if not targets:
            # Use default covergroups from profile
            profile_cgs = self.config.get("coverage", {}).get("questa", {}).get(
                "functional_covergroups", [])
            if profile_cgs:
                targets = profile_cgs[:3]  # Take first few as defaults

        return targets

    def _extract_hints(self, test: UVMTest) -> list[str]:
        """Extract hints from test description and name using AI.

        Args:
            test: UVM test

        Returns:
            List of hint strings
        """
        return self._extract_hints_with_ai(test)

    def _generate_description(self, test: UVMTest) -> str:
        """Generate task description from test using AI.

        Args:
            test: UVM test

        Returns:
            Description string
        """
        return self._generate_description_with_ai(test)

    def _generate_goal(self, test: UVMTest) -> str:
        """Generate task goal statement using AI.

        Args:
            test: UVM test

        Returns:
            Goal string
        """
        return self._generate_goal_with_ai(test)

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

    def _generate_description_with_ai(self, test: UVMTest) -> str:
        """Generate thorough task description using AI.

        Args:
            test: UVM test

        Returns:
            Human-like task description
        """
        # Read original test file for context
        test_code = ""
        if test.file_path.exists():
            with contextlib.suppress(Exception):
                test_code = test.file_path.read_text()[:3000]

        prompt = f"""You are creating a task specification for a UVM verification challenge, similar to LeetCode but for hardware verification.

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
Return ONLY the description text, no markdown, no quotes."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                temperature=0.7,
                system="You are an expert verification engineer writing task specifications. Be thorough and specific.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            description = response.content[0].text.strip()
            # Remove quotes if AI added them
            description = description.strip('"\'')
            return description

        except Exception as e:
            raise RuntimeError(f"AI description generation failed: {e}") from e

    def _generate_goal_with_ai(self, test: UVMTest) -> str:
        """Generate task goal using AI.

        Args:
            test: UVM test

        Returns:
            Goal string
        """
        prompt = f"""You are creating a task specification for a UVM verification challenge.

Test name: {test.name}
Test description: {test.description or 'Not available'}

Write a concise goal statement (1-2 sentences) that tells the user what they need to accomplish.
The goal should mention:
- Writing UVM test(s) and/or sequence(s)
- Achieving coverage targets
- The specific scenario being tested

Keep it actionable and clear. Return ONLY the goal text."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=150,
                temperature=0.6,
                system="You are an expert verification engineer. Write clear, actionable goals.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            goal = response.content[0].text.strip()
            goal = goal.strip('"\'')
            return goal

        except Exception as e:
            raise RuntimeError(f"AI goal generation failed: {e}") from e

    def _extract_hints_with_ai(self, test: UVMTest) -> list[str]:
        """Extract helpful hints using AI.

        Args:
            test: UVM test

        Returns:
            List of hint strings
        """
        # Read original test file for context
        test_code = ""
        if test.file_path.exists():
            with contextlib.suppress(Exception):
                test_code = test.file_path.read_text()[:3000]

        prompt = f"""You are creating hints for a UVM verification challenge.

Test name: {test.name}
Base class: {test.base_class}
Test description: {test.description or 'Not available'}

Test file snippet:
```systemverilog
{test_code}
```

Generate 3-5 helpful hints that guide the implementer WITHOUT giving away the solution.
Hints should mention:
- Which sequences to use or create
- Configuration parameters to set
- Key protocol features to exercise
- Testing strategies or patterns

Return a JSON array of hint strings.
Example: ["Use the base write sequence with 8-bit data width", "Configure address range to cover low addresses", "Verify strobe signals match data width"]
"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=400,
                temperature=0.7,
                system="You are an expert verification engineer. Provide helpful but not overly explicit hints.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text.strip()
            # Extract JSON if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            hints = json.loads(content)
            return hints if isinstance(hints, list) else [hints]

        except Exception as e:
            raise RuntimeError(f"AI hints generation failed: {e}") from e