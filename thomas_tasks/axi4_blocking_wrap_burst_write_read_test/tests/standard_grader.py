#!/usr/bin/env python3
"""
Enhanced pytest-based automated test grading for AXI4 coverage.

Includes:
- Functional coverage checking (existing)
- Scoreboard validation (new)
- Performance metrics (new)

Usage:
    pytest test_grade_enhanced.py --test-name=<test> --requirements=<req_file> -v -s
    python3 test_grade_enhanced.py <test> <req_file>
"""

import pytest
import subprocess
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CoverageRequirement:
    """Represents a single coverage requirement."""
    coverpoint: str
    bin_name: str
    min_coverage: float

    @classmethod
    def from_line(cls, line: str) -> Optional['CoverageRequirement']:
        """Parse requirement from text line."""
        line = line.strip()
        if not line or line.startswith('#'):
            return None

        parts = line.split('|')
        if len(parts) != 3:
            return None

        coverpoint, bin_name, min_cov = parts
        return cls(
            coverpoint=coverpoint.strip(),
            bin_name=bin_name.strip(),
            min_coverage=float(min_cov.strip())
        )


@dataclass
class CoverageBin:
    """Represents a coverage bin from IMC report."""
    name: str
    coverage: float
    hits: int


@dataclass
class ScoreboardResult:
    """Represents scoreboard validation results."""
    errors: int
    warnings: int
    fatals: int
    passed: bool
    data_mismatches: int
    total_transactions: int

    @property
    def error_free(self) -> bool:
        """True if no errors or fatals."""
        return self.errors == 0 and self.fatals == 0


@dataclass
class PerformanceMetrics:
    """Represents test performance metrics."""
    simulation_time_ns: int
    wall_clock_time_sec: float
    num_transactions: int
    coverage_percentage: float

    @property
    def efficiency(self) -> float:
        """Coverage per microsecond of simulation time."""
        if self.simulation_time_ns == 0:
            return 0.0
        return self.coverage_percentage / (self.simulation_time_ns / 1000.0)

    @property
    def transactions_per_us(self) -> float:
        """Transaction rate."""
        if self.simulation_time_ns == 0:
            return 0.0
        return self.num_transactions / (self.simulation_time_ns / 1000.0)


class LogAnalyzer:
    """Analyzes simulation log files for scoreboard and performance data."""

    def __init__(self, test_name: str, sim_dir: str = None):
        self.test_name = test_name
        self.sim_dir = sim_dir
        self.log_file = f"{test_name}/{test_name}.log"

    def analyze_scoreboard(self) -> ScoreboardResult:
        """Extract scoreboard results from log."""
        log_path = Path(self.sim_dir) / self.log_file if self.sim_dir else Path(self.log_file)
        if not log_path.exists():
            return ScoreboardResult(
                errors=999, warnings=0, fatals=999, passed=False,
                data_mismatches=999, total_transactions=0
            )

        with open(log_path, 'r') as f:
            log = f.read()

        # Count UVM messages (avoid matching summary lines like "UVM_ERROR : 0")
        # Look for actual error messages with @ or specific patterns
        errors = len(re.findall(r'UVM_ERROR @', log))
        warnings = len(re.findall(r'UVM_WARNING @', log))
        fatals = len(re.findall(r'UVM_FATAL @', log))

        # Look for scoreboard results
        # Common patterns: "Data matched", "Data mismatch", "SCOREBOARD PASSED"
        data_matches = len(re.findall(r'Data matched', log, re.IGNORECASE))
        data_mismatches = len(re.findall(r'Data mismatch', log, re.IGNORECASE))

        # Count transactions (optional - not all testbenches print this)
        write_trans = len(re.findall(r'Write.*transaction.*complet', log, re.IGNORECASE))
        read_trans = len(re.findall(r'Read.*transaction.*complet', log, re.IGNORECASE))
        total_transactions = write_trans + read_trans

        # Determine pass/fail
        # Test passes if no errors/fatals and no data mismatches
        # Note: If scoreboard doesn't print messages, we can only check errors/fatals
        passed = (errors == 0 and fatals == 0)

        return ScoreboardResult(
            errors=errors,
            warnings=warnings,
            fatals=fatals,
            passed=passed,
            data_mismatches=data_mismatches,
            total_transactions=total_transactions
        )

    def analyze_performance(self) -> PerformanceMetrics:
        """Extract performance metrics from log."""
        log_path = Path(self.sim_dir) / self.log_file if self.sim_dir else Path(self.log_file)
        if not log_path.exists():
            return PerformanceMetrics(
                simulation_time_ns=0,
                wall_clock_time_sec=0.0,
                num_transactions=0,
                coverage_percentage=0.0
            )

        with open(log_path, 'r') as f:
            log = f.read()

        # Extract simulation time
        # Pattern: "Simulation complete via $finish(1) at time 4110 NS"
        time_match = re.search(r'at time (\d+)\s*NS', log, re.IGNORECASE)
        sim_time_ns = int(time_match.group(1)) if time_match else 0

        # Alternative pattern: "$finish at simulation time 1250 ns"
        if sim_time_ns == 0:
            time_match = re.search(r'\$finish at simulation time (\d+)\s*ns', log, re.IGNORECASE)
            sim_time_ns = int(time_match.group(1)) if time_match else 0

        # Extract wall clock time (if available)
        # Pattern: "CPU time: 12.34 seconds"
        wall_match = re.search(r'CPU time:\s*([\d.]+)\s*second', log)
        wall_time = float(wall_match.group(1)) if wall_match else 0.0

        # Count transactions
        write_trans = len(re.findall(r'Write.*transaction.*complet', log, re.IGNORECASE))
        read_trans = len(re.findall(r'Read.*transaction.*complet', log, re.IGNORECASE))
        num_transactions = write_trans + read_trans

        return PerformanceMetrics(
            simulation_time_ns=sim_time_ns,
            wall_clock_time_sec=wall_time,
            num_transactions=num_transactions,
            coverage_percentage=0.0  # Will be filled in later
        )


class IMCCoverageExtractor:
    """Extracts coverage data from IMC detailed reports."""

    def __init__(self, test_name: str, sim_dir: str = None):
        self.test_name = test_name
        self.sim_dir = sim_dir
        self.report_file = f"{test_name}_detail.txt"

    def generate_report(self) -> bool:
        """Generate detailed coverage report from IMC."""
        cmd = [
            'imc',
            '-load', self.test_name,
            '-execcmd', f'report -detail -metrics functional -covered -out {self.report_file}'
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.sim_dir
            )
            report_path = Path(self.sim_dir) / self.report_file if self.sim_dir else Path(self.report_file)
            return report_path.exists()
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"ERROR: Failed to generate coverage report: {e}")
            return False

    def extract_bin_coverage(self, bin_name: str) -> Optional[CoverageBin]:
        """Extract coverage for a specific bin."""
        report_path = Path(self.sim_dir) / self.report_file if self.sim_dir else Path(self.report_file)
        if not report_path.exists():
            return None

        pattern = rf'^\| \|--{re.escape(bin_name)}\s+(\d+\.\d+)%\s+\((\d+)/\d+\)'

        with open(report_path, 'r') as f:
            for line in f:
                match = re.match(pattern, line)
                if match:
                    coverage = float(match.group(1))
                    hits = int(match.group(2))
                    return CoverageBin(name=bin_name, coverage=coverage, hits=hits)

        return CoverageBin(name=bin_name, coverage=0.0, hits=0)

    def extract_coverpoint_coverage(self, coverpoint: str) -> Optional[CoverageBin]:
        """Extract overall coverage for a coverpoint."""
        report_path = Path(self.sim_dir) / self.report_file if self.sim_dir else Path(self.report_file)
        if not report_path.exists():
            return None

        pattern = rf'^\|--{re.escape(coverpoint)}\s+(\d+\.\d+)%\s+\((\d+)/\d+\)'

        with open(report_path, 'r') as f:
            for line in f:
                match = re.match(pattern, line)
                if match:
                    coverage = float(match.group(1))
                    hits = int(match.group(2))
                    return CoverageBin(name=coverpoint, coverage=coverage, hits=hits)

        return CoverageBin(name=coverpoint, coverage=0.0, hits=0)


class EnhancedCoverageGrader:
    """Enhanced grader with scoreboard and performance checking."""

    def __init__(self, test_name: str, requirements_file: str, sim_dir: str = None):
        self.test_name = test_name
        self.requirements_file = requirements_file
        self.sim_dir = sim_dir
        self.extractor = IMCCoverageExtractor(test_name, sim_dir)
        self.log_analyzer = LogAnalyzer(test_name, sim_dir)
        self.requirements: List[CoverageRequirement] = []
        self.results: List[Tuple[CoverageRequirement, CoverageBin, bool]] = []
        self.scoreboard_result: Optional[ScoreboardResult] = None
        self.performance: Optional[PerformanceMetrics] = None

    def load_requirements(self) -> bool:
        """Load requirements from file."""
        req_path = Path(self.requirements_file)
        if not req_path.exists():
            print(f"ERROR: Requirements file not found: {self.requirements_file}")
            return False

        with open(req_path, 'r') as f:
            for line in f:
                req = CoverageRequirement.from_line(line)
                if req:
                    self.requirements.append(req)

        if not self.requirements:
            print(f"ERROR: No valid requirements found in {self.requirements_file}")
            return False

        return True

    def generate_coverage_report(self) -> bool:
        """Generate IMC coverage report."""
        return self.extractor.generate_report()

    def check_scoreboard(self) -> ScoreboardResult:
        """Check scoreboard results from log file."""
        self.scoreboard_result = self.log_analyzer.analyze_scoreboard()
        return self.scoreboard_result

    def check_performance(self, coverage_pct: float) -> PerformanceMetrics:
        """Check performance metrics from log file."""
        self.performance = self.log_analyzer.analyze_performance()
        self.performance.coverage_percentage = coverage_pct
        return self.performance

    def grade(self) -> Tuple[int, int, float]:
        """
        Grade the test against requirements.

        Returns:
            (passed_count, total_count, percentage)
        """
        self.results = []

        for req in self.requirements:
            if req.bin_name and req.bin_name != '*':
                bin_cov = self.extractor.extract_bin_coverage(req.bin_name)
            else:
                bin_cov = self.extractor.extract_coverpoint_coverage(req.coverpoint)

            if not bin_cov:
                bin_cov = CoverageBin(name=req.bin_name or req.coverpoint, coverage=0.0, hits=0)

            passed = bin_cov.coverage >= req.min_coverage
            self.results.append((req, bin_cov, passed))

        passed_count = sum(1 for _, _, passed in self.results if passed)
        total_count = len(self.results)
        percentage = (passed_count / total_count * 100) if total_count > 0 else 0.0

        return passed_count, total_count, percentage

    def print_report(self):
        """Print comprehensive grading report to console."""
        print()
        print("=" * 80)
        print("COMPREHENSIVE GRADING REPORT")
        print("=" * 80)
        print()

        # === SCOREBOARD VALIDATION ===
        print("--- SCOREBOARD VALIDATION ---")
        if self.scoreboard_result:
            sb = self.scoreboard_result
            status = "✓ PASS" if sb.passed else "✗ FAIL"
            print(f"{status}: Scoreboard check")
            print(f"       UVM Errors:   {sb.errors}")
            print(f"       UVM Warnings: {sb.warnings}")
            print(f"       UVM Fatals:   {sb.fatals}")
            print(f"       Data Mismatches: {sb.data_mismatches}")
            print(f"       Total Transactions: {sb.total_transactions}")

            if not sb.passed:
                print()
                print("       ⚠️  TEST FAILED SCOREBOARD CHECK - Coverage results may be invalid!")
        else:
            print("✗ FAIL: Could not analyze scoreboard results")
        print()

        # === COVERAGE REQUIREMENTS ===
        print("--- FUNCTIONAL COVERAGE ---")
        for req, bin_cov, passed in self.results:
            status = "✓ PASS" if passed else "✗ FAIL"
            bin_display = f" -> {req.bin_name}" if req.bin_name and req.bin_name != '*' else ""
            print(f"{status}: {req.coverpoint}{bin_display}")
            print(f"       Coverage: {bin_cov.coverage:.2f}% (required: {req.min_coverage:.0f}%)")

        passed_count = sum(1 for _, _, passed in self.results if passed)
        total_count = len(self.results)
        cov_percentage = (passed_count / total_count * 100) if total_count > 0 else 0.0
        print()

        # === PERFORMANCE METRICS ===
        print("--- PERFORMANCE METRICS ---")
        if self.performance:
            perf = self.performance
            print(f"Simulation Time:     {perf.simulation_time_ns:,} ns")
            print(f"Wall Clock Time:     {perf.wall_clock_time_sec:.2f} sec")
            print(f"Total Transactions:  {perf.num_transactions}")
            print(f"Transaction Rate:    {perf.transactions_per_us:.2f} trans/μs")
            print(f"Efficiency:          {perf.efficiency:.3f} coverage%/μs")
        else:
            print("Performance metrics not available")
        print()

        # === FINAL GRADE ===
        print("=" * 80)
        print("FINAL GRADE")
        print("=" * 80)

        # Calculate weighted grade
        # Scoreboard: 40% (must pass)
        # Coverage: 50%
        # Performance: 10% (bonus)

        scoreboard_weight = 0.4
        coverage_weight = 0.5
        performance_weight = 0.1

        scoreboard_score = 100 if (self.scoreboard_result and self.scoreboard_result.passed) else 0
        coverage_score = cov_percentage

        # Performance scoring (efficiency-based)
        performance_score = 0
        if self.performance and self.performance.efficiency > 0:
            # Efficiency > 10 coverage%/μs = excellent (100%)
            # Efficiency > 5 = good (80%)
            # Efficiency > 2 = acceptable (60%)
            # Efficiency <= 2 = poor (40%)
            eff = self.performance.efficiency
            if eff > 10:
                performance_score = 100
            elif eff > 5:
                performance_score = 80
            elif eff > 2:
                performance_score = 60
            else:
                performance_score = 40

        final_grade = (
            scoreboard_weight * scoreboard_score +
            coverage_weight * coverage_score +
            performance_weight * performance_score
        )

        print(f"Scoreboard:  {scoreboard_score:.1f}% (weight: {scoreboard_weight*100:.0f}%)")
        print(f"Coverage:    {coverage_score:.1f}% (weight: {coverage_weight*100:.0f}%)")
        print(f"Performance: {performance_score:.1f}% (weight: {performance_weight*100:.0f}%)")
        print()
        print(f"FINAL GRADE: {final_grade:.2f}%")

        if scoreboard_score == 0:
            print()
            print("⚠️  WARNING: Test failed scoreboard validation!")
            print("    Coverage metrics are meaningless if the test has functional errors.")

        print("=" * 80)
        print()

        return final_grade


# ============================================================================
# Pytest fixtures and tests
# ============================================================================

@pytest.fixture(scope="session")
def grader(request):
    """Create and initialize the enhanced grader."""
    test_name = request.config.getoption("--test-name")
    requirements = request.config.getoption("--requirements")

    if not test_name or not requirements:
        pytest.skip("--test-name and --requirements are required")

    grader = EnhancedCoverageGrader(test_name, requirements)

    if not grader.load_requirements():
        pytest.fail(f"Failed to load requirements from {requirements}")

    print(f"\nGenerating coverage report for {test_name}...")
    if not grader.generate_coverage_report():
        pytest.fail(f"Failed to generate coverage report for {test_name}")

    # Perform grading
    grader.grade()

    # Check scoreboard
    grader.check_scoreboard()

    # Check performance
    passed, total, cov_pct = grader.grade()
    grader.check_performance(cov_pct)

    return grader


def test_comprehensive_grading(grader):
    """Test comprehensive grading (scoreboard + coverage + performance)."""
    final_grade = grader.print_report()

    # Test fails if scoreboard failed OR coverage is below threshold
    assert grader.scoreboard_result.passed, \
        f"Scoreboard validation failed: {grader.scoreboard_result.errors} errors, " \
        f"{grader.scoreboard_result.fatals} fatals, {grader.scoreboard_result.data_mismatches} mismatches"

    # Check coverage requirements
    failures = []
    for req, bin_cov, passed in grader.results:
        if not passed:
            bin_display = f" -> {req.bin_name}" if req.bin_name and req.bin_name != '*' else ""
            failures.append(
                f"{req.coverpoint}{bin_display}: "
                f"{bin_cov.coverage:.2f}% < {req.min_coverage:.0f}%"
            )

    if failures:
        failure_msg = "\n".join(["\nCoverage requirements not met:"] + failures)
        pytest.fail(failure_msg)


# ============================================================================
# Standalone execution
# ============================================================================

def main():
    """Run grading from command line without pytest."""
    if len(sys.argv) != 3:
        print("Usage: python3 test_grade_enhanced.py <test_name> <requirements_file>")
        print("Example: python3 test_grade_enhanced.py axi4_blocking_32b_write_read_test exam_32b_write_read_requirements.txt")
        sys.exit(1)

    test_name = sys.argv[1]
    requirements_file = sys.argv[2]

    grader = EnhancedCoverageGrader(test_name, requirements_file)

    if not grader.load_requirements():
        sys.exit(1)

    print(f"Generating coverage report for {test_name}...")
    if not grader.generate_coverage_report():
        sys.exit(1)

    # Grade
    passed, total, cov_percentage = grader.grade()

    # Check scoreboard
    grader.check_scoreboard()

    # Check performance
    grader.check_performance(cov_percentage)

    # Print report
    final_grade = grader.print_report()

    # Exit with appropriate code
    # Fail if scoreboard failed OR not all coverage requirements met
    scoreboard_passed = grader.scoreboard_result and grader.scoreboard_result.passed
    coverage_passed = passed == total

    sys.exit(0 if (scoreboard_passed and coverage_passed) else 1)


if __name__ == "__main__":
    main()
