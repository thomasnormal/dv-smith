"""Test core data models."""

from pathlib import Path

import pytest
from dvsmith.core.models import (
    AcceptanceCriteria,
    CodeCoverage,
    CoverageBin,
    CoverageGroup,
    CoverageReport,
    EvaluationResult,
    HealthMetrics,
    Simulator,
    TaskSpec,
    UVMSequence,
    UVMTest,
)


class TestCoverageModels:
    """Test coverage-related models."""

    def test_coverage_bin_creation(self) -> None:
        """Test CoverageBin creation and calculation."""
        bin = CoverageBin(name="test_bin", hits=10, goal=20, coverage_pct=50.0)
        assert bin.name == "test_bin"
        assert bin.hits == 10
        assert bin.goal == 20
        assert bin.coverage_pct == 50.0
        assert bin.is_covered is False

    def test_coverage_bin_full_coverage(self) -> None:
        """Test bin with 100% coverage."""
        bin = CoverageBin(name="full_bin", hits=25, goal=10, coverage_pct=250.0)
        assert bin.coverage_pct == 250.0  # Over-covered
        assert bin.is_covered is True

    def test_coverage_bin_zero_goal(self) -> None:
        """Test bin with zero goal."""
        bin = CoverageBin(name="zero_goal", hits=5, goal=0, coverage_pct=0.0)
        assert bin.coverage_pct == 0.0
        assert bin.is_covered is True  # 5 >= 0

    def test_coverage_group(self) -> None:
        """Test CoverageGroup with bins."""
        bins = [
            CoverageBin(name="bin1", hits=10, goal=10, coverage_pct=100.0),
            CoverageBin(name="bin2", hits=5, goal=10, coverage_pct=50.0),
        ]
        group = CoverageGroup(name="test_group", bins=bins, overall_pct=75.0)
        assert group.name == "test_group"
        assert len(group.bins) == 2
        assert group.overall_pct == 75.0

    def test_code_coverage_defaults(self) -> None:
        """Test CodeCoverage with default values."""
        cov = CodeCoverage()
        assert cov.statements_pct == 0.0
        assert cov.branches_pct == 0.0
        assert cov.toggles_pct == 0.0
        assert cov.fsm_pct == 0.0

    def test_health_metrics(self) -> None:
        """Test HealthMetrics model."""
        health = HealthMetrics(
            uvm_errors=5,
            uvm_fatals=1,
            scoreboard_errors=3,
            assertion_failures=2
        )
        assert health.uvm_errors == 5
        assert health.uvm_fatals == 1
        assert health.scoreboard_errors == 3
        assert health.assertion_failures == 2

    def test_coverage_report(self) -> None:
        """Test complete CoverageReport."""
        report = CoverageReport(simulator=Simulator.QUESTA)
        assert report.simulator == Simulator.QUESTA
        assert len(report.functional_groups) == 0
        assert isinstance(report.code_coverage, CodeCoverage)
        assert isinstance(report.health, HealthMetrics)


class TestUVMModels:
    """Test UVM-related models."""

    def test_uvm_test_creation(self) -> None:
        """Test UVMTest model."""
        test = UVMTest(
            name="apb_write_test",
            file_path=Path("/path/to/test.sv"),
            base_class="apb_base_test",
            description="Test write operations"
        )
        assert test.name == "apb_write_test"
        assert test.file_path == Path("/path/to/test.sv")
        assert test.base_class == "apb_base_test"
        assert test.description == "Test write operations"

    def test_uvm_sequence_creation(self) -> None:
        """Test UVMSequence model."""
        seq = UVMSequence(
            name="apb_write_seq",
            file_path=Path("/path/to/seq.sv"),
            base_class="uvm_sequence"
        )
        assert seq.name == "apb_write_seq"
        assert seq.file_path == Path("/path/to/seq.sv")
        assert seq.base_class == "uvm_sequence"


class TestTaskModels:
    """Test task specification models."""

    def test_acceptance_criteria(self) -> None:
        """Test AcceptanceCriteria model."""
        criteria = AcceptanceCriteria(
            functional_bins=["cg1.bin1", "cg2.bin2"],
            functional_min_pct=80.0,
            code_statements_min_pct=70.0,
            code_branches_min_pct=60.0,
            max_uvm_errors=0,
            weights={"functional_coverage": 0.5, "code_coverage": 0.3, "health": 0.2}
        )
        assert criteria.functional_min_pct == 80.0
        assert criteria.code_statements_min_pct == 70.0
        assert criteria.max_uvm_errors == 0
        assert len(criteria.functional_bins) == 2
        assert criteria.weights["functional_coverage"] == 0.5

    def test_task_spec_to_markdown(self) -> None:
        """Test TaskSpec markdown generation."""
        from dvsmith.core.models import TaskLevel

        criteria = AcceptanceCriteria(
            functional_min_pct=80.0,
            code_statements_min_pct=70.0
        )
        task = TaskSpec(
            id="test_task_001",
            name="apb_write_test",
            level=TaskLevel.MEDIUM,
            bench_name="apb_avip",
            description="Write a UVM test for APB write operations",
            goal="Test APB write functionality",
            acceptance=criteria,
            hints=["Use apb_write_seq", "Check pready signal"]
        )

        md = task.to_markdown()
        assert "# Task: apb_write_test" in md  # Uses name not id as title
        assert "test_task_001" in md  # ID is in body
        assert "80.0" in md  # functional_min_pct
        assert "70.0" in md  # code_statements_min_pct
        assert "apb_write_seq" in md  # hint


class TestEvaluationModels:
    """Test evaluation result models."""

    def test_evaluation_result_passing(self) -> None:
        """Test passing evaluation result."""
        coverage = CoverageReport(simulator=Simulator.QUESTA)
        result = EvaluationResult(
            task_id="test_001",
            passed=True,
            score=85.5,
            coverage_report=coverage,
            functional_score=90.0,
            code_coverage_score=80.0,
            health_score=100.0
        )
        assert result.task_id == "test_001"
        assert result.passed is True
        assert result.score == 85.5
        assert result.functional_score == 90.0

    def test_evaluation_result_failing(self) -> None:
        """Test failing evaluation result."""
        coverage = CoverageReport(simulator=Simulator.QUESTA)
        result = EvaluationResult(
            task_id="test_002",
            passed=False,
            score=45.0,
            coverage_report=coverage,
            functional_score=50.0,
            code_coverage_score=40.0,
            health_score=0.0,
            functional_bins_missed=["bin1", "bin2"]
        )
        assert result.passed is False
        assert result.score == 45.0
        assert len(result.functional_bins_missed) == 2


class TestSimulatorEnum:
    """Test Simulator enum."""

    def test_simulator_values(self) -> None:
        """Test simulator enum values."""
        assert Simulator.QUESTA.value == "questa"
        assert Simulator.XCELIUM.value == "xcelium"
        assert Simulator.VCS.value == "vcs"
        assert Simulator.VERILATOR.value == "verilator"

    def test_simulator_from_string(self) -> None:
        """Test creating simulator from string."""
        assert Simulator("questa") == Simulator.QUESTA
        assert Simulator("xcelium") == Simulator.XCELIUM


if __name__ == "__main__":
    pytest.main([__file__, "-v"])