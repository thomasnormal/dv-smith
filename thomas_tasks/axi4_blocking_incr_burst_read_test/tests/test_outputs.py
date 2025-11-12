import os
import subprocess
import shutil
from pathlib import Path
from standard_grader import EnhancedCoverageGrader


def test_make_compile_simulate_and_grade():
    """Run `make compile`, `make simulate test=...` and the grader.

    Requires environment variables:
      - TB_HOME: path to the testbench home directory
      - TEST_NAME: name of the test to simulate

    The test will fail if:
      - Compilation fails
      - Simulation fails
      - Scoreboard validation fails (UVM errors/fatals)
      - Coverage requirements are not met
    """

    tb_home = Path(os.environ["TB_HOME"])
    sim_dir = tb_home / "sim" / "cadence_sim"
    test_name = os.environ["TEST_NAME"]

    # Delete existing coverage databases before compilation
    cov_work_dir = sim_dir / "cov_work"
    if cov_work_dir.exists():
        print(f"Removing existing coverage database: {cov_work_dir}")
        shutil.rmtree(cov_work_dir)

    # Compile and simulate
    subprocess.check_call(["make", "compile"], cwd=sim_dir)
    subprocess.check_call(["make", "simulate", f"test={test_name}"], cwd=sim_dir)

    # Grade with enhanced grader (pass sim_dir so it can find coverage DB and logs)
    grader = EnhancedCoverageGrader(test_name, "/resources/coverage_requirements.txt", str(sim_dir))

    assert grader.load_requirements(), "Failed to load coverage requirements"
    assert grader.generate_coverage_report(), "Failed to generate coverage report"

    # Grade coverage
    passed, total, cov_percentage = grader.grade()

    # Check scoreboard
    grader.check_scoreboard()

    # Check performance
    grader.check_performance(cov_percentage)

    # Print report for visibility
    grader.print_report()

    # Assert scoreboard passed
    assert grader.scoreboard_result.passed, \
        f"Scoreboard validation failed: {grader.scoreboard_result.errors} errors, " \
        f"{grader.scoreboard_result.fatals} fatals"

    # Assert all coverage requirements met
    assert passed == total, \
        f"Coverage requirements not met: {passed}/{total} passed ({cov_percentage:.1f}%)"

