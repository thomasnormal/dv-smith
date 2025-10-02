"""Xcelium simulator adapter."""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from ...core.models import CoverageReport, Simulator
from ..cov.xcelium_parser import XceliumCoverageParser
from .base import SimulationResult, SimulatorAdapter, SimulatorConfig


class XceliumAdapter(SimulatorAdapter):
    """Adapter for Cadence Xcelium simulator."""

    def __init__(self, repo_root: Path, profile_config: dict[str, Any]) -> None:
        """Initialize Xcelium adapter.

        Expected profile_config keys:
        - work_dir: Path to work directory
        - compile_cmd: Compilation command template
        - run_cmd: Simulation run command template
        - coverage_dir: Path to coverage database directory
        """
        super().__init__(repo_root, profile_config)
        self.parser = XceliumCoverageParser()

    def _validate_config(self) -> None:
        """Validate required config keys are present."""
        required_keys = ["work_dir", "compile_cmd", "run_cmd"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Xcelium config missing required key: {key}")

    @property
    def simulator_type(self) -> Simulator:
        """Return simulator type."""
        return Simulator.XCELIUM

    def check_available(self) -> bool:
        """Check if Xcelium is available."""
        # Check for xrun in PATH
        xrun_path = shutil.which("xrun")
        if not xrun_path:
            return False

        # Try to get version
        try:
            result = subprocess.run(
                ["xrun", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def compile(self, work_dir: Path, extra_args: Optional[dict[str, str]] = None) -> bool:
        """Compile design with Xcelium.

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

        print(f"[Xcelium] Compiling in {work_dir}")
        print(f"[Xcelium] Command: {compile_cmd}")

        try:
            result = subprocess.run(
                compile_cmd,
                shell=True,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute compile timeout
            )

            compile_log = work_dir / "compile.log"
            compile_log.write_text(result.stdout + result.stderr)

            # Check for actual errors in output (makefiles may use .IGNORE and always return 0)
            output = result.stdout + result.stderr
            has_errors = "xrun: *E," in output or "Error-" in output

            if result.returncode != 0 or has_errors:
                print(f"[Xcelium] Compilation failed. See {compile_log}")
                if has_errors:
                    # Print first few error lines
                    error_lines = [line for line in output.split('\n') if '*E,' in line or 'Error-' in line]
                    for line in error_lines[:5]:
                        print(f"  {line}")
                return False

            print("[Xcelium] Compilation successful")
            return True

        except subprocess.TimeoutExpired:
            print("[Xcelium] Compilation timed out")
            return False
        except Exception as e:
            print(f"[Xcelium] Compilation error: {e}")
            return False

    def run_test(self, sim_config: SimulatorConfig) -> SimulationResult:
        """Run a test with Xcelium.

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
            "verbosity": sim_config.uvm_verbosity
        }

        for key, value in replacements.items():
            run_cmd = run_cmd.replace(f"{{{key}}}", value)

        # Note: Coverage is typically enabled in the compile step for makefiles
        # Don't append coverage flags here as they would go to make, not xrun
        # The makefile should already have coverage configured

        log_file = sim_config.work_dir / f"{sim_config.test_name}.log"

        print(f"[Xcelium] Running test: {sim_config.test_name}")
        print(f"[Xcelium] Command: {run_cmd}")

        import time
        start_time = time.time()

        try:
            result = subprocess.run(
                run_cmd,
                shell=True,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=sim_config.timeout_sec
            )

            runtime = time.time() - start_time

            # Write log
            log_file.write_text(result.stdout + result.stderr)

            success = result.returncode == 0

            # Coverage database is created in sim directory, not work_dir
            coverage_dir = None
            if sim_config.coverage_enabled:
                # Try sim/cadence_sim/cov_work (where makefile creates it)
                sim_cov_dir = self.repo_root / "sim" / "cadence_sim" / "cov_work"
                if sim_cov_dir.exists():
                    coverage_dir = sim_cov_dir
                else:
                    # Fallback to work_dir
                    work_cov_dir = sim_config.work_dir / "cov_work"
                    if work_cov_dir.exists():
                        coverage_dir = work_cov_dir

            return SimulationResult(
                success=success,
                exit_code=result.returncode,
                log_path=log_file,
                coverage_db_path=coverage_dir,
                stdout=result.stdout,
                stderr=result.stderr,
                runtime_sec=runtime,
                timed_out=False
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
                timed_out=True
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
                timed_out=False
            )

    def extract_coverage(self, sim_result: SimulationResult) -> CoverageReport:
        """Extract coverage from Xcelium cov_work directory.

        Args:
            sim_result: Simulation result with coverage DB path

        Returns:
            Normalized CoverageReport
        """
        if not sim_result.coverage_db_path or not sim_result.coverage_db_path.exists():
            print("[Xcelium] No coverage database found")
            return CoverageReport(simulator=Simulator.XCELIUM)

        # Find the test-specific coverage directory (cov_work/scope/<testname>)
        # Look for the latest test directory under cov_work/scope/
        scope_dir = sim_result.coverage_db_path / "scope"
        if not scope_dir.exists():
            print(f"[Xcelium] Scope directory not found: {scope_dir}")
            return CoverageReport(simulator=Simulator.XCELIUM)

        # Get the most recent test directory (in case there are multiple)
        test_dirs = [d for d in scope_dir.iterdir() if d.is_dir()]
        if not test_dirs:
            print(f"[Xcelium] No test directories found in {scope_dir}")
            return CoverageReport(simulator=Simulator.XCELIUM)

        # Use the most recently modified test directory
        test_dir = max(test_dirs, key=lambda d: d.stat().st_mtime)

        # Generate text report from cov_work using IMC
        report_dir = sim_result.coverage_db_path.parent / "coverage_report"
        report_dir.mkdir(exist_ok=True)

        # Generate functional coverage report
        func_report = report_dir / "functional.txt"
        func_cmd = f"imc -execcmd 'load -run {test_dir}; report -summary -grading covered' > {func_report}"

        # Generate code coverage report
        code_report = report_dir / "code.txt"
        code_cmd = f"imc -execcmd 'load -run {test_dir}; report -summary -metrics all' > {code_report}"

        try:
            # Run functional coverage report
            subprocess.run(
                func_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Run code coverage report
            subprocess.run(
                code_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Parse the reports
            return self.parser.parse(report_dir, sim_result.log_path)

        except Exception as e:
            print(f"[Xcelium] Coverage extraction error: {e}")
            return CoverageReport(simulator=Simulator.XCELIUM)

    def merge_coverage(self, coverage_dbs: list[Path], output_path: Path) -> Path:
        """Merge multiple Xcelium coverage databases.

        Args:
            coverage_dbs: List of cov_work directory paths
            output_path: Output merged coverage directory path

        Returns:
            Path to merged database
        """
        output_path.mkdir(exist_ok=True, parents=True)

        # Use IMC to merge coverage databases
        db_list = " ".join(str(db) for db in coverage_dbs)
        merge_cmd = f"imc -exec 'merge {db_list}' -cwd {output_path}"

        print(f"[Xcelium] Merging {len(coverage_dbs)} coverage databases")

        try:
            result = subprocess.run(
                merge_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                raise RuntimeError(f"Merge failed: {result.stderr}")

            return output_path

        except Exception as e:
            raise RuntimeError(f"Coverage merge error: {e}")


# Register adapter
from .base import SimulatorRegistry

SimulatorRegistry.register(Simulator.XCELIUM, XceliumAdapter)
