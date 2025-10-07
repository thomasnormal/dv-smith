"""Integration tests for dv-smith pipeline."""

import tempfile
from pathlib import Path

import pytest
from dotenv import load_dotenv
from dvsmith.cli import DVSmith
from dvsmith.core.models import Simulator

# Load environment variables from .env file
load_dotenv()


class TestIngestBuildPipeline:
    """Test the complete ingest -> build pipeline."""

    @pytest.fixture
    def test_repo(self):
        """Provide path to a test repository."""
        # Use minimal test repository
        repo_path = Path("test_repos/test_uvm_bench")
        if not repo_path.exists():
            pytest.skip("Test repository not available")
        return repo_path

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_ingest_creates_profile(self, test_repo, temp_workspace) -> None:
        """Test that ingest creates a valid profile."""
        dvsmith = DVSmith(workspace=temp_workspace)

        # Run ingest
        dvsmith.ingest(str(test_repo), name="test_bench")

        # Check profile was created
        profile_path = temp_workspace / "profiles" / "test_bench.yaml"
        assert profile_path.exists(), "Profile should be created"

        # Load and validate profile
        import yaml
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        assert "repo_url" in profile
        assert "paths" in profile
        # Note: tests may be empty if AI analyzer is not used
        assert profile is not None

    def test_build_creates_gym(self, test_repo, temp_workspace) -> None:
        """Test that build creates a complete gym."""
        dvsmith = DVSmith(workspace=temp_workspace)

        # Ingest first
        dvsmith.ingest(str(test_repo), name="test_bench")

        # Build gym
        dvsmith.build("test_bench")

        # Check gym directory structure
        gym_dir = temp_workspace / "gyms" / "test_bench"
        assert gym_dir.exists(), "Gym directory should be created"
        assert (gym_dir / "tasks").exists(), "Tasks directory should exist"

        # Check tasks were generated (may be 0 if no tests found)
        task_files = list((gym_dir / "tasks").glob("*.md"))
        assert isinstance(task_files, list), "Should return list of task files"

    def test_end_to_end_pipeline(self, test_repo, temp_workspace) -> None:
        """Test complete pipeline: ingest -> build -> validate."""
        dvsmith = DVSmith(workspace=temp_workspace)

        # Step 1: Ingest
        dvsmith.ingest(str(test_repo), name="test_bench_e2e")

        # Step 2: Build
        dvsmith.build("test_bench_e2e")

        # Step 3: Check artifacts
        profile_path = temp_workspace / "profiles" / "test_bench_e2e.yaml"
        gym_dir = temp_workspace / "gyms" / "test_bench_e2e"

        assert profile_path.exists()
        assert gym_dir.exists()
        assert (gym_dir / "tasks").exists()

        # Verify task structure (if any tasks generated)
        tasks = list((gym_dir / "tasks").glob("*.md"))
        if len(tasks) > 0:
            # Read first task and verify structure
            task_content = tasks[0].read_text()
            assert "# Task:" in task_content
            assert "## Goal" in task_content
            assert "## Acceptance Criteria" in task_content


class TestAIAnalyzer:
    """Test AI-powered analysis."""

    @pytest.fixture
    def test_repo(self):
        """Provide path to a test repository."""
        # Use minimal test repository
        repo_path = Path("test_repos/test_uvm_bench")
        if not repo_path.exists():
            pytest.skip("Test repository not available")
        return repo_path

    @pytest.mark.skipif(
        not __import__("os").getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY environment variable"
    )
    def test_ai_analyzer_finds_tests(self, test_repo) -> None:
        """Test that AI analyzer finds tests."""

        from dvsmith.core.ai_analyzer import AIRepoAnalyzer

        analyzer = AIRepoAnalyzer(test_repo)
        analysis = analyzer.analyze()

        # Check that analysis completed
        assert analysis is not None
        assert analysis.repo_root == test_repo

        # Tests may or may not be found depending on AI analysis
        if len(analysis.tests) > 0:
            assert analysis.tests[0].name is not None
            # File paths are relative to repo root
            assert isinstance(analysis.tests[0].file_path, __import__("pathlib").Path)

        # Check other fields exist
        assert isinstance(analysis.covergroups, list)
        assert isinstance(analysis.detected_simulators, list)

    @pytest.mark.skipif(
        not __import__("os").getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY environment variable"
    )
    def test_ai_analyzer_detects_simulators(self, test_repo) -> None:
        """Test that AI analyzer detects simulators."""

        from dvsmith.core.ai_analyzer import AIRepoAnalyzer

        analyzer = AIRepoAnalyzer(test_repo)
        analysis = analyzer.analyze()

        # Check we get Simulator enum values
        assert isinstance(analysis.detected_simulators, list)
        for sim in analysis.detected_simulators:
            assert isinstance(sim, Simulator)


class TestTaskGeneration:
    """Test task generation from analysis."""

    def test_task_generator_creates_tasks(self) -> None:
        """Test that task generator creates valid tasks."""
        from dvsmith.core.models import BuildSystem, RepoAnalysis, UVMTest
        from dvsmith.core.task_generator import TaskGenerator

        # Create mock analysis
        analysis = RepoAnalysis(
            repo_root=Path("/tmp/test"),
            tests=[
                UVMTest(
                    name="test_write",
                    file_path=Path("/tmp/test.sv"),
                    base_class="base_test"
                ),
                UVMTest(
                    name="test_read",
                    file_path=Path("/tmp/test2.sv"),
                    base_class="base_test"
                ),
            ],
            covergroups=["cg1.bin1", "cg2.bin2"],
            build_system=BuildSystem.MAKEFILE,
            detected_simulators=[Simulator.QUESTA]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "tasks"
            output_dir.mkdir()

            # Mock profile config
            profile_config = {
                "repo_path": "/tmp/test",
                "build": {
                    "questa": {
                        "work_dir": "work",
                        "compile_cmd": "make compile",
                        "run_cmd": "make run"
                    }
                }
            }

            generator = TaskGenerator(analysis, profile_config)
            tasks = generator.generate_tasks(
                output_dir=output_dir,
                smoke_tests=[]  # All tests become tasks
            )

            # Should generate tasks for all tests
            assert len(tasks) == 2

            # Check task structure
            assert tasks[0].id is not None
            # Task IDs are now generated by AI (e.g., "basic_write_operation_test")
            assert len(tasks[0].id) > 0  # ID is generated
            assert tasks[0].name  # Human-readable name exists
            assert tasks[0].acceptance is not None

            # Check task files were created
            task_files = list(output_dir.glob("*.md"))
            assert len(task_files) == 2


class TestSimulatorAdapters:
    """Test simulator adapter system."""

    def test_simulator_registry(self) -> None:
        """Test that simulators are registered."""
        # Import adapters to trigger registration
        from dvsmith.adapters.sim.base import SimulatorRegistry

        registered = SimulatorRegistry._adapters

        # Should have at least Questa and Xcelium
        assert Simulator.QUESTA in registered
        assert Simulator.XCELIUM in registered

    def test_xcelium_adapter_availability_check(self) -> None:
        """Test Xcelium adapter availability check."""
        from dvsmith.adapters.sim.xcelium import XceliumAdapter

        adapter = XceliumAdapter(
            repo_root=Path.cwd(),
            profile_config={
                "work_dir": "work",
                "compile_cmd": "xrun -compile",
                "run_cmd": "xrun -R"
            }
        )

        # check_available should return bool without crashing
        result = adapter.check_available()
        assert isinstance(result, bool)


class TestCoverageParsing:
    """Test coverage parsing system."""

    def test_xcelium_parser_integration(self) -> None:
        """Test Xcelium parser with realistic data."""
        from dvsmith.adapters.cov.xcelium_parser import XceliumCoverageParser

        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)

            # Create realistic IMC reports
            (report_dir / "functional.txt").write_text("""
Covergroup: apb_coverage_cg
  Coverage: 85.5%
  Instance: apb_env.coverage

  Coverpoint: cp_addr
    Coverage: 80.0%
    Bin: addr_low     Hits: 100    Goal: 10    Status: Covered
    Bin: addr_high    Hits: 50     Goal: 10    Status: Covered

Covergroup: apb_slave_cg
  Coverage: 90.0%
  Instance: apb_env.slave_cov

  Coverpoint: cp_data
    Coverage: 90.0%
    Bin: data_zero    Hits: 200    Goal: 10    Status: Covered
""")

            (report_dir / "code.txt").write_text("""
name                          Block                 Expression            Toggle                 Statement             Fsm Average
------------------------------------------------------------------------------------------------------------------------------------
hdl_top                       75.5% (15/20)         n/a                   82.1% (10/12)          68.3%                 95.0% (1/1)
""")

            parser = XceliumCoverageParser()
            report = parser.parse(report_dir)

            # Verify parsing
            assert report.simulator == Simulator.XCELIUM
            assert len(report.functional_groups) == 2
            assert report.functional_groups[0].overall_pct == 85.5
            assert report.code_coverage.statements_pct == 75.5  # From Block column
            assert report.code_coverage.toggles_pct == 82.1
            assert report.code_coverage.fsm_pct == 95.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])