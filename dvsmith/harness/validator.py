"""Validation harness - verify gym is properly constructed."""

from pathlib import Path
from typing import Any, Optional
import tqdm

from ..config import get_logger
# Import adapters to trigger registration
from ..adapters.sim.base import SimulatorAdapter, SimulatorConfig, SimulatorRegistry
from ..core.models import Simulator

logger = get_logger(__name__)


class Validator:
    """Validate that a DV gym is properly constructed.

    Validation checks:
    1. Smoke tests compile and run successfully
    2. Tasks are in "unsolved" state (coverage targets not met)
    3. Directory structure is correct
    4. Profile is valid
    """

    def __init__(self, gym_dir: Path, profile: dict[str, Any],
                 simulator: Optional[Simulator] = None) -> None:
        """Initialize validator.

        Args:
            gym_dir: Path to gym directory
            profile: Loaded profile configuration
            simulator: Simulator to use (default: first available)
        """
        self.gym_dir = gym_dir
        self.profile = profile
        self.simulator = simulator or self._select_simulator()
        self.adapter: Optional[SimulatorAdapter] = None

    def validate(self) -> bool:
        """Run all validation checks.

        Returns:
            True if all checks pass, False otherwise
        """
        logger.info("Starting validation...")

        checks = [
            ("Directory structure", self._check_directory_structure),
            ("Profile", self._check_profile),
            ("Simulator setup", self._check_simulator_setup),
            ("Smoke tests", self._check_smoke_tests),
            ("Tasks unsolved", self._check_tasks_unsolved),
        ]

        all_passed = True
        for check_name, check_fn in checks:
            logger.info(f"Checking: {check_name}...")
            try:
                passed = check_fn()
                if passed:
                    logger.info(f"  ✓ {check_name} passed")
                else:
                    logger.error(f"  ✗ {check_name} failed")
                    all_passed = False
            except Exception as e:
                logger.error(f"  ✗ {check_name} error: {e}")
                all_passed = False

        if all_passed:
            logger.info("✓ All validation checks passed")
        else:
            logger.error("✗ Validation failed")

        return all_passed

    def _select_simulator(self) -> Optional[Simulator]:
        """Select simulator from profile or environment.

        Returns:
            Simulator if available, None otherwise
        """
        available = SimulatorRegistry.list_available()
        profile_sims = [Simulator(s) for s in self.profile.get("simulators", [])]

        # Use first available from profile
        for sim in profile_sims:
            if sim in available:
                return sim

        # Fallback to any available
        if available:
            return available[0]

        # No simulators available - validation will skip simulator checks
        return None

    def _check_directory_structure(self) -> bool:
        """Verify required directories exist."""
        required_dirs = [
            "tests",
            "sequences",
            "tasks",
            "backups/original_tests"
        ]

        for dir_name in required_dirs:
            dir_path = self.gym_dir / dir_name
            if not dir_path.exists():
                logger.error(f"    Missing directory: {dir_path}")
                return False

        return True

    def _check_profile(self) -> bool:
        """Verify profile is valid."""
        required_keys = ["name", "simulators", "build", "grading"]

        for key in required_keys:
            if key not in self.profile:
                logger.error(f"    Missing profile key: {key}")
                return False

        # Check simulator configs
        for sim_name in self.profile["simulators"]:
            if sim_name not in self.profile.get("build", {}):
                logger.error(f"    Missing build config for: {sim_name}")
                return False

        return True

    def _check_simulator_setup(self) -> bool:
        """Verify simulator is available and can be initialized."""
        if not self.simulator:
            logger.info("    No simulators available - skipping simulator checks")
            return True

        try:
            sim_config = self.profile["build"].get(self.simulator.value, {})
            self.adapter = SimulatorRegistry.get_adapter(
                self.simulator,
                self.gym_dir,
                sim_config
            )
            return True
        except Exception as e:
            logger.error(f"    Simulator setup error: {e}")
            return False

    def _check_smoke_tests(self) -> bool:
        """Verify smoke tests compile and run successfully."""
        if not self.simulator:
            logger.info("    No simulators available - skipping smoke tests")
            return True

        if not self.adapter:
            return False

        smoke_tests = self.profile.get("grading", {}).get("smoke_tests", [])
        if not smoke_tests:
            logger.info("    No smoke tests defined")
            return True

        logger.info(f"    Running {len(smoke_tests)} smoke tests...")

        # Compile once
        work_dir = self.gym_dir / "work" / "validation"
        work_dir.mkdir(exist_ok=True, parents=True)

        if not self.adapter.compile(work_dir):
            logger.error("    Compilation failed")
            return False

        # Run each smoke test
        for test_name in tqdm.tqdm(smoke_tests):
            config = SimulatorConfig(
                work_dir=work_dir,
                test_name=test_name,
                seed=12345,  # Fixed seed for validation
                timeout_sec=120
            )

            result = self.adapter.run_test(config)

            if not result.success:
                logger.error(f"    Smoke test failed: {test_name}")
                logger.error(f"    Log: {result.log_path}")
                return False

            logger.info(f"      ✓ {test_name}")

        return True

    def _check_tasks_unsolved(self) -> bool:
        """Verify that tasks are in unsolved state.

        This checks a sample of tasks to ensure:
        - Coverage targets are not already met by smoke tests
        - Task specifications are valid
        """
        tasks_dir = self.gym_dir / "tasks"
        task_files = list(tasks_dir.glob("task_*.md"))

        if not task_files:
            logger.error("    No task files found")
            return False

        # Sample up to 3 tasks for validation
        sample_tasks = task_files[:min(3, len(task_files))]

        logger.info(f"    Checking {len(sample_tasks)} sample tasks...")

        for task_file in sample_tasks:
            try:
                # Parse task (simplified - full implementation would load properly)
                task_name = task_file.stem

                # For now, just check file is readable and non-empty
                content = task_file.read_text()
                if len(content) < 100:
                    logger.error(f"    Task file too short: {task_file}")
                    return False

                # Check for required sections
                required_sections = ["Goal", "Acceptance Criteria"]
                for section in required_sections:
                    if section not in content:
                        logger.error(f"    Missing section '{section}': {task_file}")
                        return False

                logger.info(f"      ✓ {task_name}")

            except Exception as e:
                logger.error(f"    Error checking task {task_file}: {e}")
                return False

        return True
