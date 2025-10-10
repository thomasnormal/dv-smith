"""Questa/ModelSim simulator adapter."""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from ...config import get_logger
from ...core.models import CoverageReport, Simulator
from ..cov.questa_parser import QuestaCovrageParser
from .base import SimulationResult, SimulatorAdapter, SimulatorConfig

logger = get_logger(__name__)


class QuestaAdapter(SimulatorAdapter):
    """Adapter for Questa/ModelSim simulator."""

    def __init__(self, repo_root: Path, profile_config: dict[str, Any]) -> None:
        """Initialize Questa adapter.

        Expected profile_config keys:
        - work_dir: Path to work directory
        - compile_cmd: Compilation command template
        - run_cmd: Simulation run command template
        - coverage_db: Path to coverage database (UCDB)
        """
        super().__init__(repo_root, profile_config)
        self.parser = QuestaCovrageParser()

    def _validate_config(self) -> None:
        """Validate required config keys are present."""
        required_keys = ["work_dir", "compile_cmd", "run_cmd"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Questa config missing required key: {key}")

    @property
    def simulator_type(self) -> Simulator:
        """Return simulator type."""
        return Simulator.QUESTA

    def check_available(self) -> bool:
        """Check if Questa is available."""
        # Check for vsim in PATH
        vsim_path = shutil.which("vsim")
        if not vsim_path:
            return False

        # Try to get version
        try:
            result = subprocess.run(["vsim", "-version"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def compile(self, work_dir: Path, extra_args: Optional[dict[str, str]] = None) -> bool:
        """Compile design with Questa.

        Args:
            work_dir: Working directory for compilation
            extra_args: Optional extra arguments

        Returns:
            True if compilation succeeded
        """
        work_dir.mkdir(exist_ok=True, parents=True)

        # Format compile command from profile
        compile_cmd = self.config["compile_cmd"]

        # Replace any template variables
        if extra_args:
            for key, value in extra_args.items():
                compile_cmd = compile_cmd.replace(f"{{{key}}}", value)

        logger.info(f"Compiling in {work_dir}")
        logger.debug(f"Command: {compile_cmd}")

        try:
            result = subprocess.run(
                compile_cmd,
                shell=True,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute compile timeout
            )

            compile_log = work_dir / "compile.log"
            compile_log.write_text(result.stdout + result.stderr)

            if result.returncode != 0:
                logger.error(f"Compilation failed. See {compile_log}")
                logger.debug(result.stderr)
                return False

            logger.info("Compilation successful")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Compilation timed out")
            return False
        except Exception as e:
            logger.error(f"Compilation error: {e}")
            return False

    def run_test(self, sim_config: SimulatorConfig) -> SimulationResult:
        """Run a test with Questa.

        Args:
            sim_config: Simulation configuration

        Returns:
            SimulationResult with outcomes and paths
        """
        sim_config.work_dir.mkdir(exist_ok=True, parents=True)

        # Format run command from profile
        run_cmd = self.config["run_cmd"]

        # Replace template variables
        replacements = {
            "test": sim_config.test_name,
            "seed": str(sim_config.seed) if sim_config.seed else "random",
            "verbosity": sim_config.uvm_verbosity,
        }

        for key, value in replacements.items():
            run_cmd = run_cmd.replace(f"{{{key}}}", value)

        # Add coverage options if enabled
        if sim_config.coverage_enabled:
            coverage_db = sim_config.work_dir / "coverage.ucdb"
            # Add coverage save command to dofile
            do_file = sim_config.work_dir / "run.do"
            do_file.write_text(
                f"""
coverage save -onexit {coverage_db}
run -all
quit
"""
            )
            run_cmd += f" -do {do_file}"

        log_file = sim_config.work_dir / f"{sim_config.test_name}.log"

        logger.info(f"Running test: {sim_config.test_name}")
        logger.debug(f"Command: {run_cmd}")

        import time

        start_time = time.time()

        try:
            result = subprocess.run(
                run_cmd,
                shell=True,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=sim_config.timeout_sec,
            )

            runtime = time.time() - start_time

            # Write log
            log_file.write_text(result.stdout + result.stderr)

            success = result.returncode == 0
            coverage_db = (
                sim_config.work_dir / "coverage.ucdb" if sim_config.coverage_enabled else None
            )

            return SimulationResult(
                success=success,
                exit_code=result.returncode,
                log_path=log_file,
                coverage_db_path=coverage_db if coverage_db and coverage_db.exists() else None,
                stdout=result.stdout,
                stderr=result.stderr,
                runtime_sec=runtime,
                timed_out=False,
            )

        except subprocess.TimeoutExpired:
            runtime = time.time() - start_time
            log_file.write_text("TIMEOUT: Simulation exceeded time limit")

            return SimulationResult(
                success=False,
                exit_code=-1,
                log_path=log_file,
                coverage_db_path=None,
                runtime_sec=runtime,
                timed_out=True,
            )

        except Exception as e:
            runtime = time.time() - start_time
            log_file.write_text(f"ERROR: {e!s}")

            return SimulationResult(
                success=False,
                exit_code=-1,
                log_path=log_file,
                coverage_db_path=None,
                runtime_sec=runtime,
                timed_out=False,
            )

    def extract_coverage(self, sim_result: SimulationResult) -> CoverageReport:
        """Extract coverage from Questa UCDB.

        Args:
            sim_result: Simulation result with coverage DB path

        Returns:
            Normalized CoverageReport
        """
        if not sim_result.coverage_db_path or not sim_result.coverage_db_path.exists():
            logger.warning("No coverage database found")
            return CoverageReport(simulator=Simulator.QUESTA)

        # Generate text report from UCDB
        report_file = sim_result.coverage_db_path.parent / "coverage_report.txt"
        report_cmd = (
            f"vcover report -details -thresh 0 -output {report_file} {sim_result.coverage_db_path}"
        )

        try:
            result = subprocess.run(
                report_cmd, shell=True, capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0:
                logger.error(f"Coverage report generation failed: {result.stderr}")
                return CoverageReport(simulator=Simulator.QUESTA)

            # Parse the report
            return self.parser.parse(report_file, sim_result.log_path)

        except Exception as e:
            logger.error(f"Coverage extraction error: {e}")
            return CoverageReport(simulator=Simulator.QUESTA)

    def merge_coverage(self, coverage_dbs: list[Path], output_path: Path) -> Path:
        """Merge multiple UCDB files.

        Args:
            coverage_dbs: List of UCDB paths
            output_path: Output merged UCDB path

        Returns:
            Path to merged database
        """
        db_list = " ".join(str(db) for db in coverage_dbs)
        merge_cmd = f"vcover merge -output {output_path} {db_list}"

        logger.info(f"Merging {len(coverage_dbs)} coverage databases")

        try:
            result = subprocess.run(
                merge_cmd, shell=True, capture_output=True, text=True, timeout=300
            )

            if result.returncode != 0:
                raise RuntimeError(f"Merge failed: {result.stderr}")

            return output_path

        except Exception as e:
            raise RuntimeError(f"Coverage merge error: {e}")


# Register adapter
from .base import SimulatorRegistry

SimulatorRegistry.register(Simulator.QUESTA, QuestaAdapter)
