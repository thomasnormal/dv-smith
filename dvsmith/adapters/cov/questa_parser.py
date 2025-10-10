"""Parser for Questa/ModelSim coverage reports."""

import re
from pathlib import Path
from typing import Optional

from ...config import get_logger
from ...core.models import (
    CodeCoverage,
    CoverageBin,
    CoverageGroup,
    CoverageReport,
    Simulator,
)
from ..parse.uvm_log import UVMLogParser

logger = get_logger(__name__)


class QuestaCovrageParser:
    """Parse Questa vcover report output into normalized CoverageReport."""

    def __init__(self) -> None:
        """Initialize parser."""
        self.log_parser = UVMLogParser()

    def parse(self, report_path: Path, log_path: Optional[Path] = None) -> CoverageReport:
        """Parse Questa coverage report.

        Args:
            report_path: Path to vcover report text file
            log_path: Optional path to simulation log for health metrics

        Returns:
            Normalized CoverageReport
        """
        report = CoverageReport(simulator=Simulator.QUESTA, raw_report_path=report_path)

        if not report_path.exists():
            return report

        try:
            content = report_path.read_text()

            # Parse functional coverage (covergroups)
            report.functional_groups = self._parse_functional_coverage(content)

            # Parse code coverage
            report.code_coverage = self._parse_code_coverage(content)

            # Parse health metrics from log if available
            if log_path and log_path.exists():
                report.health = self.log_parser.parse_health(log_path)

        except Exception as e:
            logger.error(f"Error parsing coverage: {e}")

        return report

    def _parse_functional_coverage(self, content: str) -> list[CoverageGroup]:
        """Parse functional coverage groups and bins from vcover report.

        The vcover report format typically looks like:

        COVERGROUP COVERAGE:
        =============================================
        Covergroup                        Metric        Goal    Status
        =============================================
        apb_master_coverage/apb_tx_cg      67.5%       100.0%   Uncovered

          Coverpoint cp_paddr               75.0%       100.0%   Uncovered
            bin paddr_low                      10          1   Covered
            bin paddr_mid                       5          1   Covered
            bin paddr_high                      0          1   ZERO
        """
        groups = []

        # Find covergroup sections
        # Pattern: covergroup name followed by percentage
        cg_pattern = re.compile(r"^(\S+/\S+|\w+)\s+(\d+\.?\d*)%\s+(\d+\.?\d*)%", re.MULTILINE)

        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # Look for covergroup
            cg_match = cg_pattern.match(line.strip())
            if cg_match and "/" in cg_match.group(1):
                cg_name = cg_match.group(1)
                overall_pct = float(cg_match.group(2))

                # Parse bins for this covergroup
                bins = []
                i += 1

                # Look ahead for bins
                while i < len(lines):
                    bin_line = lines[i].strip()

                    # Bin pattern: "bin name    hits    goal    status"
                    bin_match = re.match(r"bin\s+(\w+)\s+(\d+)\s+(\d+)", bin_line)

                    if bin_match:
                        bin_name = bin_match.group(1)
                        hits = int(bin_match.group(2))
                        goal = int(bin_match.group(3))
                        coverage_pct = (hits / goal * 100.0) if goal > 0 else 0.0

                        bins.append(
                            CoverageBin(
                                name=bin_name, hits=hits, goal=goal, coverage_pct=coverage_pct
                            )
                        )
                        i += 1
                    elif bin_line.startswith("bin "):
                        # Alternative bin format
                        i += 1
                    elif bin_line and not bin_line.startswith(("Coverpoint", "Cross")):
                        break
                    else:
                        i += 1

                groups.append(CoverageGroup(name=cg_name, bins=bins, overall_pct=overall_pct))
                continue

            i += 1

        return groups

    def _parse_code_coverage(self, content: str) -> CodeCoverage:
        """Parse code coverage metrics from vcover report.

        Looks for sections like:

        CODE COVERAGE SUMMARY:
        =============================================
        Statement Coverage: 75.3%
        Branch Coverage: 68.2%
        Toggle Coverage: 82.1%
        FSM Coverage: 90.0%
        """
        code_cov = CodeCoverage()

        # Patterns for different coverage types
        patterns = {
            "statements_pct": r"Statement\s+Coverage:\s*(\d+\.?\d*)%",
            "branches_pct": r"Branch\s+Coverage:\s*(\d+\.?\d*)%",
            "toggles_pct": r"Toggle\s+Coverage:\s*(\d+\.?\d*)%",
            "fsm_pct": r"FSM\s+Coverage:\s*(\d+\.?\d*)%",
            "expressions_pct": r"Expression\s+Coverage:\s*(\d+\.?\d*)%",
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                setattr(code_cov, field, float(match.group(1)))

        return code_cov
