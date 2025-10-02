"""Parser for Xcelium IMC coverage reports."""

import re
from pathlib import Path
from typing import Optional

from ...core.models import (
    CodeCoverage,
    CoverageBin,
    CoverageGroup,
    CoverageReport,
    Simulator,
)
from ..parse.uvm_log import UVMLogParser


class XceliumCoverageParser:
    """Parse Xcelium IMC coverage reports into normalized CoverageReport."""

    def __init__(self) -> None:
        """Initialize parser."""
        self.log_parser = UVMLogParser()

    def parse(self, report_path: Path, log_path: Optional[Path] = None) -> CoverageReport:
        """Parse Xcelium coverage report.

        Args:
            report_path: Path to IMC report directory or text file
            log_path: Optional path to simulation log for health metrics

        Returns:
            Normalized CoverageReport
        """
        report = CoverageReport(simulator=Simulator.XCELIUM, raw_report_path=report_path)

        # If report_path is a directory, look for functional and code coverage files
        if report_path.is_dir():
            functional_file = report_path / "functional.txt"
            code_file = report_path / "code.txt"

            if functional_file.exists():
                functional_content = functional_file.read_text()
                report.functional_groups = self._parse_functional_coverage(functional_content)

            if code_file.exists():
                code_content = code_file.read_text()
                report.code_coverage = self._parse_code_coverage(code_content)
        elif report_path.exists():
            # Single file containing all coverage
            content = report_path.read_text()
            report.functional_groups = self._parse_functional_coverage(content)
            report.code_coverage = self._parse_code_coverage(content)

        # Parse health metrics from log if available
        if log_path and log_path.exists():
            report.health = self.log_parser.parse_health(log_path)

        return report

    def _parse_functional_coverage(self, content) -> list[CoverageGroup]:
        """Parse functional coverage groups and bins from IMC report.

        Args:
            content: Either a string or Path to the functional coverage report

        Xcelium IMC functional coverage format (table):
        name                                     Functional Average   Functional Covered
        | | | |--apb_master_cov_h                21.18%               4.83% (7/145)
        """
        groups = []

        # Handle Path input
        if isinstance(content, Path):
            content = content.read_text()

        # Split content into lines
        lines = content.split("\n")

        for line in lines:
            # Skip header and separator lines
            if not line or "---" in line or "name" in line.lower():
                continue

            # Look for lines with coverage data (contain % and parentheses with bin counts)
            if "%" in line and "(" in line and "/" in line:
                # Parse hierarchical name (remove tree characters)
                parts = line.split()
                if not parts:
                    continue

                # Extract name (first non-tree element)
                name = None
                for part in parts:
                    if part and not part.startswith(('|', '-')):
                        name = part
                        break

                if not name or name == "n/a":
                    continue

                # Find functional coverage columns (last occurrence of percentage and bin count)
                # Format: "21.18%               4.83% (7/145)"
                # We want the percentage and bin count from "Functional Covered" column
                match = re.search(r'(\d+\.?\d*)%\s+\((\d+)/(\d+)\)\s*$', line)
                if match:
                    pct = float(match.group(1))
                    bins_met = int(match.group(2))
                    bins_total = int(match.group(3))

                    # Create bins based on met/total
                    bins = []
                    for i in range(bins_met):
                        bins.append(CoverageBin(name=f"bin_{i}", hits=1, goal=1, coverage_pct=100.0))
                    for i in range(bins_total - bins_met):
                        bins.append(CoverageBin(name=f"bin_{bins_met + i}", hits=0, goal=1, coverage_pct=0.0))

                    # Create coverage group (use last part of hierarchical name)
                    instance_name = name
                    group_name = name.replace("_h", "").replace("_cov", "")  # Clean up name

                    groups.append(CoverageGroup(
                        name=f"{instance_name}.{group_name}_covergroup",
                        overall_pct=pct,
                        bins=bins
                    ))

            i = 0

        # Deduplicate by name
        seen = set()
        unique_groups = []
        for g in groups:
            if g.name not in seen:
                seen.add(g.name)
                unique_groups.append(g)

        return unique_groups

    def _parse_functional_coverage_old(self, content) -> list[CoverageGroup]:
        """Old parser - kept for reference."""
        groups = []

        # Handle Path input
        if isinstance(content, Path):
            content = content.read_text()

        # Split content into lines
        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Look for "Covergroup:" line
            if line.startswith("Covergroup:"):
                cg_name = line.split(":", 1)[1].strip()
                instance_name = None
                overall_pct = 0.0
                bins = []
                i += 1

                # Parse covergroup details
                while i < len(lines):
                    line = lines[i].strip()

                    # Stop when we hit next covergroup
                    if line.startswith("Covergroup:"):
                        break

                    # Get overall coverage percentage (first Coverage: line for the group)
                    if line.startswith("Coverage:") and overall_pct == 0.0:
                        cov_match = re.search(r"(\d+\.?\d*)%", line)
                        if cov_match:
                            overall_pct = float(cov_match.group(1))

                    # Get instance name
                    elif line.startswith("Instance:"):
                        instance_name = line.split(":", 1)[1].strip()

                    # Parse bin entries
                    elif line.startswith("Bin:"):
                        # Format: Bin: bin_name    Hits: 10    Goal: 1    Status: Covered
                        bin_match = re.match(
                            r"Bin:\s+(\S+)\s+Hits:\s+(\d+)\s+Goal:\s+(\d+)",
                            line
                        )
                        if bin_match:
                            bin_name = bin_match.group(1)
                            hits = int(bin_match.group(2))
                            goal = int(bin_match.group(3))
                            coverage_pct = (hits / goal * 100.0) if goal > 0 else 0.0

                            bins.append(CoverageBin(
                                name=bin_name,
                                hits=hits,
                                goal=goal,
                                coverage_pct=coverage_pct
                            ))

                    i += 1

                # Add covergroup if we found data
                if overall_pct > 0 or bins:
                    # Format name as instance.covergroup if instance is available
                    full_name = f"{instance_name}.{cg_name}" if instance_name else cg_name
                    groups.append(CoverageGroup(
                        name=full_name,
                        bins=bins,
                        overall_pct=overall_pct
                    ))
                continue

            i += 1

        return groups

    def _parse_code_coverage(self, content) -> CodeCoverage:
        """Parse code coverage metrics from IMC report.

        Args:
            content: Either a string or Path to the code coverage report

        Xcelium IMC code coverage format (table):
        name                     Block            Expression       Toggle           Statement
        hdl_top                  93.75% (15/16)   n/a              100.00% (2/2)    n/a
        """
        code_cov = CodeCoverage()

        # Handle Path input
        if isinstance(content, Path):
            content = content.read_text()

        lines = content.split("\n")

        # Find header line to get column positions
        header_line = None
        header_idx = -1
        for i, line in enumerate(lines):
            if "Block" in line and "Expression" in line and "Toggle" in line:
                header_line = line
                header_idx = i
                break

        if not header_line:
            return code_cov

        # Get column positions from header
        col_positions = {
            'Block': header_line.find('Block'),
            'Expression': header_line.find('Expression'),
            'Toggle': header_line.find('Toggle'),
            'Statement': header_line.find('Statement'),
            'Fsm': header_line.find('Fsm Average'),
        }

        # Filter valid columns
        cols = {k: v for k, v in col_positions.items() if v >= 0}

        # Collect values
        block_vals = []
        expr_vals = []
        toggle_vals = []
        stmt_vals = []
        fsm_vals = []

        # Parse data lines (skip header, separator, and batch mode lines)
        for i, line in enumerate(lines):
            if i <= header_idx + 1:  # Skip header and separator
                continue
            if not line or "batch mode" in line.lower() or "IMC(" in line:
                continue

            # Extract percentages with their positions
            for match in re.finditer(r'(\d+\.?\d*)%', line):
                val = float(match.group(1))
                pos = match.start()

                # Determine which column based on position
                if 'Block' in cols and abs(pos - cols['Block']) < 20:
                    block_vals.append(val)
                elif 'Expression' in cols and abs(pos - cols['Expression']) < 20:
                    expr_vals.append(val)
                elif 'Toggle' in cols and abs(pos - cols['Toggle']) < 20:
                    toggle_vals.append(val)
                elif 'Statement' in cols and abs(pos - cols['Statement']) < 20:
                    stmt_vals.append(val)
                elif 'Fsm' in cols and abs(pos - cols['Fsm']) < 20:
                    fsm_vals.append(val)

        # Use average of hardware coverage (exclude UVM/testbench)
        if block_vals:
            code_cov.statements_pct = sum(block_vals) / len(block_vals)
        if expr_vals:
            code_cov.expressions_pct = sum(expr_vals) / len(expr_vals)
        if toggle_vals:
            code_cov.toggles_pct = sum(toggle_vals) / len(toggle_vals)
        if fsm_vals:
            code_cov.fsm_pct = sum(fsm_vals) / len(fsm_vals)

        # Branch coverage approximation (use block if no explicit branch)
        if block_vals and not code_cov.branches_pct:
            code_cov.branches_pct = sum(block_vals) / len(block_vals)

        return code_cov
