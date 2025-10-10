"""Evaluation harness - grade solutions against tasks."""

import subprocess
from pathlib import Path
from typing import Any, Optional

from ..config import get_logger

# Import adapters to trigger registration
from ..adapters.sim.base import SimulatorConfig, SimulatorRegistry
from ..core.models import (
    AcceptanceCriteria,
    CoverageReport,
    EvaluationResult,
    Simulator,
    TaskSpec,
)

logger = get_logger(__name__)


class Evaluator:
    """Evaluate agent solutions against task specifications."""

    def __init__(
        self, gym_dir: Path, profile: dict[str, Any], simulator: Optional[Simulator] = None
    ) -> None:
        """Initialize evaluator.

        Args:
            gym_dir: Path to gym directory
            profile: Loaded profile configuration
            simulator: Simulator to use (default: first available)
        """
        self.gym_dir = gym_dir
        self.profile = profile
        self.simulator = simulator or self._select_simulator()

        # Get simulator adapter
        sim_config = self.profile["build"].get(self.simulator.value, {})
        self.adapter = SimulatorRegistry.get_adapter(self.simulator, self.gym_dir, sim_config)

    def evaluate(
        self, task: TaskSpec, patch_path: Path, work_dir: Optional[Path] = None
    ) -> EvaluationResult:
        """Evaluate a solution against a task.

        Args:
            task: Task specification
            patch_path: Path to solution patch file
            work_dir: Working directory (default: create temp)

        Returns:
            EvaluationResult with score and details
        """
        if work_dir is None:
            work_dir = self.gym_dir / "work" / "eval" / task.id

        work_dir.mkdir(exist_ok=True, parents=True)

        logger.info(f"Evaluating task: {task.id}")

        # 1. Apply patch
        if not self._apply_patch(task, patch_path):
            return self._failure_result(task, "Patch application failed")

        # 2. Compile
        if not self.adapter.compile(work_dir):
            return self._failure_result(task, "Compilation failed")

        # 3. Run test (using test name from task or inferred)
        test_name = self._infer_test_name(task)
        config = SimulatorConfig(
            work_dir=work_dir,
            test_name=test_name,
            seed=task.acceptance.weights.get("seed", None),  # Can add seed to acceptance
            coverage_enabled=True,
        )

        sim_result = self.adapter.run_test(config)

        if not sim_result.success:
            return self._failure_result(task, "Simulation failed", sim_result.log_path)

        # 4. Extract coverage
        coverage = self.adapter.extract_coverage(sim_result)

        # 5. Compute score
        result = self._score(task, coverage, sim_result.log_path, sim_result.coverage_db_path)

        # 6. Persist artifacts (result.json, logs, coverage DB)
        self._persist_artifacts(work_dir, result)

        return result

    def _apply_patch(self, task: TaskSpec, patch_path: Path) -> bool:
        """Apply patch to gym.

        Args:
            task: Task specification
            patch_path: Path to patch file

        Returns:
            True if patch applied successfully
        """
        # Convert to absolute path since git apply runs with cwd=gym_dir
        abs_patch_path = patch_path.resolve()

        try:
            result = subprocess.run(
                ["git", "apply", "--check", str(abs_patch_path)],
                cwd=self.gym_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"Patch check failed: {result.stderr}")
                return False

            # Apply the patch
            result = subprocess.run(
                ["git", "apply", str(abs_patch_path)],
                cwd=self.gym_dir,
                capture_output=True,
                text=True,
            )

            return result.returncode == 0

        except Exception as e:
            logger.error(f"Patch application error: {e}")
            return False

    def _infer_test_name(self, task: TaskSpec) -> str:
        """Infer test name from task.

        Args:
            task: Task specification

        Returns:
            Test name
        """
        # Try to extract test name from original test file path
        if task.original_test_files:
            # Get filename without extension
            test_file = task.original_test_files[0]
            test_name = test_file.stem  # e.g., "apb_8b_write_test" from "apb_8b_write_test.sv"
            return test_name

        # Fallback: use task ID + _test
        return f"{task.id}_test"

    def _score(
        self,
        task: TaskSpec,
        coverage: CoverageReport,
        log_path: Optional[Path],
        coverage_db_path: Optional[Path],
    ) -> EvaluationResult:
        """Compute score for a solution.

        Args:
            task: Task specification
            coverage: Coverage report
            log_path: Path to simulation log
            coverage_db_path: Path to coverage database

        Returns:
            EvaluationResult
        """
        acceptance = task.acceptance

        # Compute component scores
        functional_score = self._score_functional(coverage, acceptance)
        code_score = self._score_code_coverage(coverage, acceptance)
        health_score = self._score_health(coverage, acceptance)

        # Weighted total
        total_score = (
            functional_score * acceptance.weights["functional_coverage"]
            + code_score * acceptance.weights["code_coverage"]
            + health_score * acceptance.weights["health"]
        )

        # Check if passed (all thresholds met)
        passed = self._check_passed(coverage, acceptance)

        # Track which bins were met
        bins_met, bins_missed = self._check_bins(coverage, acceptance)

        # Detailed threshold checks
        thresholds_met = {
            "functional_coverage": functional_score >= 0.99,  # Near 1.0
            "code_coverage": code_score >= 0.99,
            "health": health_score >= 0.99,
        }

        return EvaluationResult(
            task_id=task.id,
            passed=passed,
            score=total_score,
            coverage_report=coverage,
            functional_score=functional_score,
            code_coverage_score=code_score,
            health_score=health_score,
            functional_bins_met=bins_met,
            functional_bins_missed=bins_missed,
            thresholds_met=thresholds_met,
            log_path=log_path,
            coverage_db_path=coverage_db_path,
        )

    def _score_functional(self, coverage: CoverageReport, acceptance: AcceptanceCriteria) -> float:
        """Score functional coverage (0.0 to 1.0).

        Args:
            coverage: Coverage report
            acceptance: Acceptance criteria

        Returns:
            Score between 0.0 and 1.0
        """
        if not acceptance.functional_bins:
            return 1.0  # No requirements

        target_bins = acceptance.functional_bins
        strategy = acceptance.functional_strategy
        min_pct = acceptance.functional_min_pct

        if strategy == "any_of":
            # At least one target bin/group meets threshold
            max_pct = 0.0
            for bin_name in target_bins:
                pct = self._get_bin_coverage(coverage, bin_name)
                max_pct = max(max_pct, pct)

            # Normalize: if max_pct >= min_pct, score is 1.0
            # Otherwise, proportional
            return min(1.0, max_pct / min_pct) if min_pct > 0 else 0.0

        else:  # all_of
            # All target bins must meet threshold
            total_score = 0.0
            for bin_name in target_bins:
                pct = self._get_bin_coverage(coverage, bin_name)
                bin_score = min(1.0, pct / min_pct) if min_pct > 0 else 0.0
                total_score += bin_score

            return total_score / len(target_bins) if target_bins else 0.0

    def _score_code_coverage(
        self, coverage: CoverageReport, acceptance: AcceptanceCriteria
    ) -> float:
        """Score code coverage (0.0 to 1.0).

        Args:
            coverage: Coverage report
            acceptance: Acceptance criteria

        Returns:
            Score between 0.0 and 1.0
        """
        code_cov = coverage.code_coverage

        # Score each metric
        stmt_score = (
            min(1.0, code_cov.statements_pct / acceptance.code_statements_min_pct)
            if acceptance.code_statements_min_pct > 0
            else 0.0
        )

        branch_score = (
            min(1.0, code_cov.branches_pct / acceptance.code_branches_min_pct)
            if acceptance.code_branches_min_pct > 0
            else 0.0
        )

        toggle_score = (
            min(1.0, code_cov.toggles_pct / acceptance.code_toggles_min_pct)
            if acceptance.code_toggles_min_pct > 0
            else 0.0
        )

        # Average (could be weighted)
        return (stmt_score + branch_score + toggle_score) / 3.0

    def _score_health(self, coverage: CoverageReport, acceptance: AcceptanceCriteria) -> float:
        """Score health (0.0 or 1.0).

        Args:
            coverage: Coverage report
            acceptance: Acceptance criteria

        Returns:
            1.0 if healthy, 0.0 otherwise
        """
        health = coverage.health

        if health.uvm_errors > acceptance.max_uvm_errors:
            return 0.0

        if health.uvm_fatals > acceptance.max_uvm_fatals:
            return 0.0

        if health.scoreboard_errors > acceptance.max_scoreboard_errors:
            return 0.0

        if acceptance.all_assertions_pass and health.assertion_failures > 0:
            return 0.0

        return 1.0

    def _check_passed(self, coverage: CoverageReport, acceptance: AcceptanceCriteria) -> bool:
        """Check if solution passes all criteria.

        Args:
            coverage: Coverage report
            acceptance: Acceptance criteria

        Returns:
            True if passed
        """
        # Must score 1.0 on all components (with tiny tolerance)
        functional_ok = self._score_functional(coverage, acceptance) >= 0.99
        code_ok = self._score_code_coverage(coverage, acceptance) >= 0.99
        health_ok = self._score_health(coverage, acceptance) >= 0.99

        return functional_ok and code_ok and health_ok

    def _check_bins(self, coverage: CoverageReport, acceptance: AcceptanceCriteria) -> tuple:
        """Check which bins met/missed targets.

        Returns:
            (bins_met, bins_missed)
        """
        bins_met = []
        bins_missed = []

        for bin_name in acceptance.functional_bins:
            pct = self._get_bin_coverage(coverage, bin_name)
            if pct >= acceptance.functional_min_pct:
                bins_met.append(bin_name)
            else:
                bins_missed.append(bin_name)

        return bins_met, bins_missed

    def _get_bin_coverage(self, coverage: CoverageReport, bin_name: str) -> float:
        """Get coverage percentage for a bin or group.

        Args:
            coverage: Coverage report
            bin_name: Bin or group name (may be qualified like "group.bin")

        Returns:
            Coverage percentage
        """
        # Try to find as group first
        group = coverage.get_group(bin_name)
        if group:
            return group.overall_pct

        # Try as qualified bin (group.bin)
        if "." in bin_name:
            group_name, bin_name_only = bin_name.rsplit(".", 1)
            group = coverage.get_group(group_name)
            if group:
                bin_obj = group.get_bin(bin_name_only)
                if bin_obj:
                    return bin_obj.coverage_pct

        return 0.0

    def _failure_result(
        self, task: TaskSpec, reason: str, log_path: Optional[Path] = None
    ) -> EvaluationResult:
        """Create a failure result.

        Args:
            task: Task specification
            reason: Failure reason
            log_path: Optional log path

        Returns:
            EvaluationResult with failure
        """
        logger.error(f"Evaluation failed: {reason}")

        return EvaluationResult(
            task_id=task.id,
            passed=False,
            score=0.0,
            coverage_report=CoverageReport(),
            functional_score=0.0,
            code_coverage_score=0.0,
            health_score=0.0,
            log_path=log_path,
        )

    def _persist_artifacts(self, work_dir: Path, result: EvaluationResult) -> None:
        """Persist evaluation artifacts to work directory.

        Args:
            work_dir: Working directory for this evaluation
            result: Evaluation result to persist

        Saves:
            - result.json: Compact JSON summary of evaluation
            - Logs, coverage DB paths already tracked in result
        """
        try:
            # Save result.json
            result_json_path = work_dir / "result.json"
            result_json_path.write_text(result.to_json())
            logger.info(f"Saved result to {result_json_path}")

            # Log paths are already in result (log_path, coverage_db_path)
            # These can be used for leaderboards, analysis, etc.

        except Exception as e:
            logger.warning(f"Could not persist artifacts: {e}")

    def _select_simulator(self) -> Simulator:
        """Select simulator from profile or environment."""
        available = SimulatorRegistry.list_available()
        profile_sims = [Simulator(s) for s in self.profile.get("simulators", [])]

        for sim in profile_sims:
            if sim in available:
                return sim

        if available:
            return available[0]

        raise RuntimeError("No simulators available")
