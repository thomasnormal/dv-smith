"""Parser for UVM simulation logs."""

import re
from pathlib import Path

from ...config import get_logger
from ...core.models import HealthMetrics

logger = get_logger(__name__)


class UVMLogParser:
    """Parse UVM simulation logs for health metrics."""

    def parse_health(self, log_path: Path) -> HealthMetrics:
        """Parse health metrics from UVM log.

        Args:
            log_path: Path to simulation log file

        Returns:
            HealthMetrics with error/warning counts
        """
        metrics = HealthMetrics()

        if not log_path.exists():
            return metrics

        try:
            content = log_path.read_text()

            # Count UVM errors and fatals
            metrics.uvm_errors = self._count_uvm_errors(content)
            metrics.uvm_fatals = self._count_uvm_fatals(content)
            metrics.uvm_warnings = self._count_uvm_warnings(content)

            # Count scoreboard errors
            metrics.scoreboard_errors = self._count_scoreboard_errors(content)

            # Count assertion failures
            metrics.assertion_failures = self._count_assertion_failures(content)

            # Check for timeout
            metrics.simulation_timeout = self._check_timeout(content)

            # Compilation errors (from log)
            metrics.compilation_errors = self._count_compilation_errors(content)

        except Exception as e:
            logger.error(f"Error parsing log: {e}")

        return metrics

    def _count_uvm_errors(self, content: str) -> int:
        """Count UVM_ERROR occurrences."""
        # Pattern: UVM_ERROR or *** UVM_ERROR
        pattern = r"UVM_ERROR(?:\s+@|\s+:|\s*\])"
        return len(re.findall(pattern, content, re.IGNORECASE))

    def _count_uvm_fatals(self, content: str) -> int:
        """Count UVM_FATAL occurrences."""
        pattern = r"UVM_FATAL(?:\s+@|\s+:|\s*\])"
        return len(re.findall(pattern, content, re.IGNORECASE))

    def _count_uvm_warnings(self, content: str) -> int:
        """Count UVM_WARNING occurrences."""
        pattern = r"UVM_WARNING(?:\s+@|\s+:|\s*\])"
        return len(re.findall(pattern, content, re.IGNORECASE))

    def _count_scoreboard_errors(self, content: str) -> int:
        """Count scoreboard error messages.

        Looks for common scoreboard error patterns like:
        - "scoreboard error"
        - "mismatch"
        - "compare failed"
        """
        patterns = [
            r"scoreboard.*?error",
            r"scoreboard.*?mismatch",
            r"compare\s+failed",
            r"data\s+mismatch",
        ]

        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, content, re.IGNORECASE))

        return count

    def _count_assertion_failures(self, content: str) -> int:
        """Count assertion failures.

        Looks for patterns like:
        - "Assertion failed"
        - "Error: Assertion"
        - SystemVerilog assertion messages
        """
        patterns = [
            r"assertion\s+failed",
            r"error:.*?assertion",
            r"fatal:.*?assertion",
            r"\*\*\s*Error.*?assert",
        ]

        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, content, re.IGNORECASE))

        return count

    def _check_timeout(self, content: str) -> bool:
        """Check if simulation timed out."""
        timeout_patterns = [
            r"timeout",
            r"time.*?limit.*?exceeded",
            r"simulation.*?killed",
        ]

        for pattern in timeout_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def _count_compilation_errors(self, content: str) -> int:
        """Count compilation errors in log."""
        # This assumes compilation messages might be in same log
        patterns = [
            r"\*\*\s*Error:",
            r"compilation\s+failed",
            r"syntax\s+error",
        ]

        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, content, re.IGNORECASE))

        return count

    def extract_coverage_counters(self, log_path: Path) -> dict[str, int]:
        """Extract functional coverage counters from log messages.

        Useful for open-source simulators that don't have full
        covergroup support (e.g., Verilator).

        Looks for user-defined counter messages like:
        - "[COUNTER] burst_type_incr: 15"
        - "[COV] addr_aligned: 23"

        Args:
            log_path: Path to simulation log

        Returns:
            Dictionary of counter name -> count
        """
        counters = {}

        if not log_path.exists():
            return counters

        try:
            content = log_path.read_text()

            # Pattern: [COUNTER] or [COV] followed by name: value
            pattern = r"\[(COUNTER|COV)\]\s+(\w+):\s+(\d+)"

            for match in re.finditer(pattern, content):
                name = match.group(2)
                value = int(match.group(3))
                counters[name] = value

        except Exception as e:
            logger.error(f"Error extracting counters: {e}")

        return counters
