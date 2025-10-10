"""Base simulator adapter interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from tqdm import tqdm

from ...core.models import CoverageReport, Simulator


@dataclass
class SimulatorConfig:
    """Configuration for a simulator run."""
    work_dir: Path
    test_name: str
    seed: Optional[int] = None
    uvm_verbosity: str = "UVM_MEDIUM"
    timeout_sec: int = 300
    extra_args: dict[str, str] = None
    coverage_enabled: bool = True


@dataclass
class SimulationResult:
    """Result of a simulation run."""
    success: bool
    exit_code: int
    log_path: Path
    coverage_db_path: Optional[Path] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    runtime_sec: float = 0.0
    timed_out: bool = False


class SimulatorAdapter(ABC):
    """Abstract base class for simulator adapters.

    Each simulator (Questa, Xcelium, VCS, Verilator) implements this interface
    to provide a uniform API for compilation, simulation, and coverage extraction.
    """

    def __init__(self, repo_root: Path, profile_config: dict[str, Any]) -> None:
        """Initialize adapter with repository and profile configuration.

        Args:
            repo_root: Path to repository root
            profile_config: Simulator-specific config from RepoProfile
        """
        self.repo_root = repo_root
        self.config = profile_config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate that required config keys are present."""
        pass

    @property
    @abstractmethod
    def simulator_type(self) -> Simulator:
        """Return the simulator type."""
        pass

    @abstractmethod
    def check_available(self) -> bool:
        """Check if simulator is available (installed and licensed).

        Returns:
            True if simulator can be used, False otherwise
        """
        pass

    @abstractmethod
    def compile(self, work_dir: Path, extra_args: Optional[dict[str, str]] = None) -> bool:
        """Compile the design and testbench.

        Args:
            work_dir: Working directory for compilation artifacts
            extra_args: Optional extra compilation arguments

        Returns:
            True if compilation succeeded, False otherwise
        """
        pass

    @abstractmethod
    def run_test(self, sim_config: SimulatorConfig) -> SimulationResult:
        """Run a single test.

        Args:
            sim_config: Configuration for the simulation run

        Returns:
            SimulationResult with outcome and artifact paths
        """
        pass

    @abstractmethod
    def extract_coverage(self, sim_result: SimulationResult) -> CoverageReport:
        """Extract and normalize coverage from simulation artifacts.

        Args:
            sim_result: Result from run_test containing coverage DB path

        Returns:
            Normalized CoverageReport
        """
        pass

    @abstractmethod
    def merge_coverage(self, coverage_dbs: list[Path], output_path: Path) -> Path:
        """Merge multiple coverage databases.

        Args:
            coverage_dbs: List of coverage database paths to merge
            output_path: Where to write merged database

        Returns:
            Path to merged coverage database
        """
        pass

    def run_regression(self, tests: list[str], work_dir: Path,
                      seeds: Optional[list[int]] = None) -> list[SimulationResult]:
        """Run multiple tests (regression).

        Default implementation runs tests sequentially. Subclasses can override
        for parallel execution.

        Args:
            tests: List of test names to run
            work_dir: Working directory
            seeds: Optional list of seeds (one per test, or used for all)

        Returns:
            List of SimulationResults
        """
        results = []
        for i, test in tqdm(enumerate(tests), total=len(tests), desc="Running regression", unit="test"):
            seed = seeds[i] if seeds and i < len(seeds) else None
            config = SimulatorConfig(
                work_dir=work_dir,
                test_name=test,
                seed=seed
            )
            result = self.run_test(config)
            results.append(result)
        return results

    def cleanup(self, work_dir: Path) -> None:
        """Clean up simulation artifacts (optional).

        Args:
            work_dir: Directory to clean
        """
        pass


class SimulatorRegistry:
    """Registry for available simulator adapters."""

    _adapters: dict[Simulator, type] = {}

    @classmethod
    def register(cls, simulator: Simulator, adapter_class: type) -> None:
        """Register a simulator adapter class.

        Args:
            simulator: Simulator type
            adapter_class: Adapter class implementing SimulatorAdapter
        """
        if not issubclass(adapter_class, SimulatorAdapter):
            raise TypeError(f"{adapter_class} must inherit from SimulatorAdapter")
        cls._adapters[simulator] = adapter_class

    @classmethod
    def get_adapter(cls, simulator: Simulator, repo_root: Path,
                   profile_config: dict[str, Any]) -> SimulatorAdapter:
        """Get an adapter instance for a simulator.

        Args:
            simulator: Simulator type
            repo_root: Repository root path
            profile_config: Configuration from profile

        Returns:
            Instantiated simulator adapter

        Raises:
            ValueError: If simulator not registered or unavailable
        """
        if simulator not in cls._adapters:
            raise ValueError(f"No adapter registered for {simulator}")

        adapter_class = cls._adapters[simulator]
        adapter = adapter_class(repo_root, profile_config)

        if not adapter.check_available():
            raise ValueError(f"{simulator} is not available (not installed or licensed)")

        return adapter

    @classmethod
    def list_available(cls) -> list[Simulator]:
        """List all available (installed) simulators.

        Returns:
            List of available simulator types
        """
        available = []
        for sim_type, adapter_class in cls._adapters.items():
            # Try to instantiate with minimal config to check availability
            try:
                adapter = adapter_class(Path("."), {})
                if adapter.check_available():
                    available.append(sim_type)
            except:
                pass
        return available