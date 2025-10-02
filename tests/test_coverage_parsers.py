"""Test coverage parsers."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from dvsmith.adapters.cov.questa_parser import QuestaCovrageParser
from dvsmith.adapters.cov.xcelium_parser import XceliumCoverageParser
from dvsmith.core.models import Simulator


class TestQuestaCoverageParser:
    """Test Questa vcover parser."""

    def test_parser_instantiation(self) -> None:
        """Test parser can be instantiated."""
        parser = QuestaCovrageParser()
        assert parser is not None

    def test_parse_functional_coverage(self) -> None:
        """Test parsing functional coverage."""
        parser = QuestaCovrageParser()

        # Mock vcover report content - format matches actual vcover output
        content = """
Covergroup Coverage:
======================================
apb_master_coverage/apb_master_cg    75.00%    100.00%
  Coverpoint cp_paddr
    bin paddr_low    10    10
    bin paddr_mid    5     5
    bin paddr_high   0     1

apb_slave_coverage/apb_slave_cg      100.00%   100.00%
  Coverpoint cp_psel
    bin psel_active  25    25
    bin psel_idle    10    10
"""
        groups = parser._parse_functional_coverage(content)
        assert len(groups) == 2
        assert groups[0].name == "apb_master_coverage/apb_master_cg"
        assert groups[0].overall_pct == 75.0
        assert len(groups[0].bins) == 3

        # Check first bin
        assert groups[0].bins[0].name == "paddr_low"
        assert groups[0].bins[0].hits == 10
        assert groups[0].bins[0].goal == 10
        assert groups[0].bins[0].coverage_pct == 100.0

    def test_parse_code_coverage(self) -> None:
        """Test parsing code coverage."""
        parser = QuestaCovrageParser()

        content = """
Code Coverage Summary:
======================================
Statement Coverage: 85.3%
Branch Coverage: 72.1%
Toggle Coverage: 91.5%
"""
        code_cov = parser._parse_code_coverage(content)
        assert code_cov.statements_pct == 85.3
        assert code_cov.branches_pct == 72.1
        assert code_cov.toggles_pct == 91.5


class TestXceliumCoverageParser:
    """Test Xcelium IMC parser."""

    def test_parser_instantiation(self) -> None:
        """Test parser can be instantiated."""
        parser = XceliumCoverageParser()
        assert parser is not None

    def test_parse_functional_coverage_from_file(self) -> None:
        """Test parsing functional coverage from IMC report file."""
        parser = XceliumCoverageParser()

        with TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "reports"
            report_dir.mkdir()

            # Create mock functional.txt
            functional_report = report_dir / "functional.txt"
            functional_report.write_text("""
Covergroup: apb_master_cg
  Coverage: 67.5%
  Instance: apb_master_coverage

  Coverpoint: cp_paddr
    Coverage: 75.0%
    Bin: paddr_low    Hits: 10    Goal: 1    Status: Covered
    Bin: paddr_mid    Hits: 5     Goal: 1    Status: Covered
    Bin: paddr_high   Hits: 0     Goal: 1    Status: ZERO

Covergroup: apb_slave_cg
  Coverage: 100.0%
  Instance: apb_slave_coverage

  Coverpoint: cp_psel
    Coverage: 100.0%
    Bin: psel_active   Hits: 25    Goal: 1    Status: Covered
""")

            # Use old parser for text-based functional coverage
            groups = parser._parse_functional_coverage_old(functional_report)
            assert len(groups) == 2

            # Check first covergroup
            assert groups[0].name == "apb_master_coverage.apb_master_cg"
            assert groups[0].overall_pct == 67.5
            assert len(groups[0].bins) == 3

            # Check bins
            assert groups[0].bins[0].name == "paddr_low"
            assert groups[0].bins[0].hits == 10
            assert groups[0].bins[0].goal == 1
            assert groups[0].bins[0].coverage_pct == 1000.0  # 10/1 * 100

            # Check second covergroup
            assert groups[1].name == "apb_slave_coverage.apb_slave_cg"
            assert groups[1].overall_pct == 100.0
            assert len(groups[1].bins) == 1

    def test_parse_code_coverage_from_file(self) -> None:
        """Test parsing code coverage from IMC code report."""
        parser = XceliumCoverageParser()

        with TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            code_report = report_dir / "code.txt"
            code_report.write_text("""
name                          Block                 Expression            Toggle                 Statement             Fsm Average
------------------------------------------------------------------------------------------------------------------------------------
hdl_top                       85.3% (15/16)         n/a                   91.5% (2/2)            72.1%                 100.0% (1/1)
apb_slave                     90.0% (9/10)          n/a                   85.0% (17/20)          80.0%                 n/a
""")

            code_cov = parser._parse_code_coverage(code_report)
            # Parser averages all values from the table
            assert code_cov.statements_pct == 87.65  # (85.3 + 90.0) / 2 from Block
            assert code_cov.toggles_pct == 88.25  # (91.5 + 85.0) / 2
            assert code_cov.fsm_pct == 100.0

    def test_parse_full_report(self) -> None:
        """Test parsing complete IMC report."""
        parser = XceliumCoverageParser()

        with TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)

            # Create functional report
            (report_dir / "functional.txt").write_text("""
Covergroup: test_cg
  Coverage: 80.0%
  Instance: test_inst
  Bin: bin1    Hits: 8    Goal: 10    Status: Partial
""")

            # Create code report
            (report_dir / "code.txt").write_text("""
name                     Block            Expression       Toggle           Statement
---------------------------------------------------------------------------------------
hdl_top                  90.0% (15/16)    n/a              n/a              85.0%
""")

            # Parse full report
            report = parser.parse(report_dir)

            assert report.simulator == Simulator.XCELIUM
            assert len(report.functional_groups) == 1
            assert report.functional_groups[0].name == "test_inst.test_cg"
            assert report.code_coverage.statements_pct == 90.0
            assert report.code_coverage.branches_pct == 90.0  # Uses Block column

    def test_parse_summary_fallback(self) -> None:
        """Test parsing from summary when code.txt missing."""
        parser = XceliumCoverageParser()

        with TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)

            # Only create summary (no code.txt)
            (report_dir / "summary.txt").write_text("""
Coverage Summary:
Statement    1234/5000    75.0%
Branch       567/890      65.0%
Toggle       2345/3000    80.0%
""")

            report = parser.parse(report_dir)
            assert report.code_coverage.statements_pct == 75.0
            assert report.code_coverage.branches_pct == 65.0
            assert report.code_coverage.toggles_pct == 80.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])