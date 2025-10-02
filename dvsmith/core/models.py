"""Core data models for dv-smith."""

import contextlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Simulator(str, Enum):
    """Supported simulators."""
    QUESTA = "questa"
    XCELIUM = "xcelium"
    VCS = "vcs"
    VERILATOR = "verilator"
    DSIM = "dsim"


class BuildSystem(str, Enum):
    """Detected build system types."""
    MAKEFILE = "makefile"
    CMAKE = "cmake"
    DVSIM = "dvsim"
    FUSESOC = "fusesoc"
    CUSTOM = "custom"


class TaskLevel(str, Enum):
    """Task difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class CoverageBin:
    """Individual coverage bin information."""
    name: str
    hits: int
    goal: int
    coverage_pct: float

    @property
    def is_covered(self) -> bool:
        return self.hits >= self.goal


@dataclass
class CoverageGroup:
    """Functional coverage group with bins."""
    name: str
    bins: list[CoverageBin]
    overall_pct: float

    def get_bin(self, name: str) -> Optional[CoverageBin]:
        """Find bin by name."""
        return next((b for b in self.bins if b.name == name), None)


@dataclass
class CodeCoverage:
    """Code coverage metrics."""
    statements_pct: float = 0.0
    branches_pct: float = 0.0
    toggles_pct: float = 0.0
    fsm_pct: float = 0.0
    expressions_pct: float = 0.0


@dataclass
class HealthMetrics:
    """Simulation health/quality metrics."""
    uvm_errors: int = 0
    uvm_fatals: int = 0
    uvm_warnings: int = 0
    scoreboard_errors: int = 0
    assertion_failures: int = 0
    simulation_timeout: bool = False
    compilation_errors: int = 0

    @property
    def is_healthy(self) -> bool:
        """Check if simulation is in healthy state."""
        return (self.uvm_errors == 0 and
                self.uvm_fatals == 0 and
                self.scoreboard_errors == 0 and
                self.assertion_failures == 0 and
                not self.simulation_timeout and
                self.compilation_errors == 0)


@dataclass
class CoverageReport:
    """Normalized coverage report across all simulators."""
    functional_groups: list[CoverageGroup] = field(default_factory=list)
    code_coverage: CodeCoverage = field(default_factory=CodeCoverage)
    health: HealthMetrics = field(default_factory=HealthMetrics)
    raw_report_path: Optional[Path] = None
    simulator: Optional[Simulator] = None

    def get_group(self, name: str) -> Optional[CoverageGroup]:
        """Find coverage group by name."""
        return next((g for g in self.functional_groups if g.name == name), None)

    def to_json(self) -> str:
        """Serialize to JSON."""
        data = {
            "functional_groups": [
                {
                    "name": g.name,
                    "overall_pct": g.overall_pct,
                    "bins": [
                        {
                            "name": b.name,
                            "hits": b.hits,
                            "goal": b.goal,
                            "coverage_pct": b.coverage_pct
                        } for b in g.bins
                    ]
                } for g in self.functional_groups
            ],
            "code_coverage": {
                "statements_pct": self.code_coverage.statements_pct,
                "branches_pct": self.code_coverage.branches_pct,
                "toggles_pct": self.code_coverage.toggles_pct,
                "fsm_pct": self.code_coverage.fsm_pct,
                "expressions_pct": self.code_coverage.expressions_pct,
            },
            "health": {
                "uvm_errors": self.health.uvm_errors,
                "uvm_fatals": self.health.uvm_fatals,
                "uvm_warnings": self.health.uvm_warnings,
                "scoreboard_errors": self.health.scoreboard_errors,
                "assertion_failures": self.health.assertion_failures,
                "simulation_timeout": self.health.simulation_timeout,
                "compilation_errors": self.health.compilation_errors,
                "is_healthy": self.health.is_healthy
            },
            "simulator": self.simulator.value if self.simulator else None
        }
        return json.dumps(data, indent=2)


@dataclass
class UVMTest:
    """Discovered UVM test information."""
    name: str
    file_path: Path
    base_class: str
    sequences_used: list[str] = field(default_factory=list)
    description: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class UVMSequence:
    """Discovered UVM sequence information."""
    name: str
    file_path: Path
    base_class: str
    description: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class RepoAnalysis:
    """Results of repository analysis."""
    tests: list[UVMTest] = field(default_factory=list)
    sequences: list[UVMSequence] = field(default_factory=list)
    covergroups: list[str] = field(default_factory=list)
    build_system: Optional[BuildSystem] = None
    detected_simulators: list[Simulator] = field(default_factory=list)
    repo_root: Optional[Path] = None

    # Path hints
    tests_dir: Optional[Path] = None
    sequences_dir: Optional[Path] = None
    env_dir: Optional[Path] = None
    agents_dir: Optional[Path] = None

    def get_test(self, name: str) -> Optional[UVMTest]:
        """Find test by name."""
        return next((t for t in self.tests if t.name == name), None)


@dataclass
class AcceptanceCriteria:
    """Task acceptance criteria."""
    functional_bins: list[str] = field(default_factory=list)
    functional_min_pct: float = 80.0
    functional_strategy: str = "any_of"  # or "all_of"

    code_statements_min_pct: float = 70.0
    code_branches_min_pct: float = 60.0
    code_toggles_min_pct: float = 50.0

    max_scoreboard_errors: int = 0
    max_uvm_errors: int = 0
    max_uvm_fatals: int = 0
    all_assertions_pass: bool = True

    weights: dict[str, float] = field(default_factory=lambda: {
        "functional_coverage": 0.6,
        "code_coverage": 0.3,
        "health": 0.1
    })


@dataclass
class TaskSpec:
    """Task specification."""
    id: str
    name: str
    level: TaskLevel
    bench_name: str
    description: str
    goal: str
    acceptance: AcceptanceCriteria
    hints: list[str] = field(default_factory=list)
    original_test_files: list[Path] = field(default_factory=list)
    supported_simulators: list[Simulator] = field(default_factory=list)
    notes: Optional[str] = None

    def to_markdown(self) -> str:
        """Generate markdown task specification."""
        lines = [
            f"# Task: {self.name}",
            "",
            f"**ID:** `{self.id}`  ",
            f"**Level:** {self.level.value}  ",
            f"**Bench:** {self.bench_name}  ",
            f"**Simulators:** {', '.join(s.value for s in self.supported_simulators)}",
            "",
            "## Goal",
            self.goal,
            "",
            "## Description",
            self.description,
            ""
        ]

        if self.hints:
            lines.extend([
                "## Hints",
                ""
            ])
            for hint in self.hints:
                lines.append(f"- {hint}")
            lines.append("")

        lines.extend([
            "## Acceptance Criteria",
            "",
            "### Functional Coverage",
            f"- **Strategy:** {self.acceptance.functional_strategy}",
            f"- **Minimum:** {self.acceptance.functional_min_pct}%",
            "- **Target bins/groups:**"
        ])

        for bin_name in self.acceptance.functional_bins:
            lines.append(f"  - `{bin_name}`")

        lines.extend([
            "",
            "### Code Coverage",
            f"- Statements: ≥{self.acceptance.code_statements_min_pct}%",
            f"- Branches: ≥{self.acceptance.code_branches_min_pct}%",
            f"- Toggles: ≥{self.acceptance.code_toggles_min_pct}%",
            "",
            "### Health",
            f"- UVM Errors: ≤{self.acceptance.max_uvm_errors}",
            f"- UVM Fatals: ≤{self.acceptance.max_uvm_fatals}",
            f"- Scoreboard Errors: ≤{self.acceptance.max_scoreboard_errors}",
            f"- Assertions: {'All must pass' if self.acceptance.all_assertions_pass else 'Allow failures'}",
            "",
            "### Scoring Weights",
            f"- Functional Coverage: {self.acceptance.weights['functional_coverage']:.1%}",
            f"- Code Coverage: {self.acceptance.weights['code_coverage']:.1%}",
            f"- Health: {self.acceptance.weights['health']:.1%}",
            ""
        ])

        if self.notes:
            lines.extend([
                "## Notes",
                self.notes,
                ""
            ])

        if self.original_test_files:
            lines.extend([
                "## Reference",
                "Original test files (for auditing only, not compiled):",
                ""
            ])
            for file_path in self.original_test_files:
                lines.append(f"- `{file_path}`")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def from_markdown(content: str) -> "TaskSpec":
        """Parse TaskSpec from markdown content.

        Args:
            content: Markdown content of task file

        Returns:
            TaskSpec object

        Raises:
            ValueError: If required fields are missing
        """
        import re

        lines = content.split("\n")

        # Extract basic fields
        task_name = ""
        task_id = ""
        level = TaskLevel.MEDIUM
        bench_name = ""
        simulators = []

        # Parse header
        for line in lines[:20]:
            if line.startswith("# Task:"):
                task_name = line.replace("# Task:", "").strip()
            elif "**ID:**" in line:
                match = re.search(r"\*\*ID:\*\*\s*`([^`]+)`", line)
                if match:
                    task_id = match.group(1)
            elif "**Level:**" in line:
                match = re.search(r"\*\*Level:\*\*\s*(\w+)", line)
                if match:
                    try:
                        level = TaskLevel(match.group(1))
                    except ValueError:
                        level = TaskLevel.MEDIUM
            elif "**Bench:**" in line:
                match = re.search(r"\*\*Bench:\*\*\s*(\S+)", line)
                if match:
                    bench_name = match.group(1)
            elif "**Simulators:**" in line:
                sim_str = line.split("**Simulators:**")[1].strip()
                for sim_name in sim_str.split(","):
                    with contextlib.suppress(ValueError):
                        simulators.append(Simulator(sim_name.strip()))

        # Extract sections
        goal = TaskSpec._extract_section(content, "Goal")
        description = TaskSpec._extract_section(content, "Description")
        notes = TaskSpec._extract_section(content, "Notes")

        # Extract hints
        hints = []
        hints_section = TaskSpec._extract_section(content, "Hints")
        if hints_section:
            for line in hints_section.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    hints.append(line[1:].strip())

        # Extract acceptance criteria
        acceptance = TaskSpec._parse_acceptance_criteria(content)

        # Extract original test files
        original_files = []
        ref_section = TaskSpec._extract_section(content, "Reference")
        if ref_section:
            for line in ref_section.split("\n"):
                if line.strip().startswith("- `") and line.strip().endswith("`"):
                    path_str = line.strip()[3:-1]
                    original_files.append(Path(path_str))

        if not task_id:
            raise ValueError("Task ID not found in markdown")
        if not task_name:
            raise ValueError("Task name not found in markdown")

        return TaskSpec(
            id=task_id,
            name=task_name,
            level=level,
            bench_name=bench_name,
            description=description or "",
            goal=goal or "",
            acceptance=acceptance,
            hints=hints,
            original_test_files=original_files,
            supported_simulators=simulators,
            notes=notes
        )

    @staticmethod
    def _extract_section(content: str, section_name: str) -> Optional[str]:
        """Extract content of a markdown section.

        Args:
            content: Full markdown content
            section_name: Section header name (without ##)

        Returns:
            Section content or None
        """
        import re

        # Find section start
        pattern = rf"^##\s+{section_name}\s*$"
        lines = content.split("\n")

        section_lines = []
        in_section = False

        for line in lines:
            if re.match(pattern, line):
                in_section = True
                continue
            elif in_section:
                if line.startswith("##"):
                    break
                section_lines.append(line)

        if section_lines:
            return "\n".join(section_lines).strip()
        return None

    @staticmethod
    def _parse_acceptance_criteria(content: str) -> AcceptanceCriteria:
        """Parse acceptance criteria from markdown.

        Args:
            content: Full markdown content

        Returns:
            AcceptanceCriteria object
        """
        import re

        # Extract functional coverage settings
        functional_strategy = "any_of"
        functional_min_pct = 80.0
        functional_bins = []

        strategy_match = re.search(r"-\s+\*\*Strategy:\*\*\s*(\w+)", content)
        if strategy_match:
            functional_strategy = strategy_match.group(1)

        min_pct_match = re.search(r"-\s+\*\*Minimum:\*\*\s*(\d+(?:\.\d+)?)%", content)
        if min_pct_match:
            functional_min_pct = float(min_pct_match.group(1))

        # Extract target bins/groups
        in_bins = False
        for line in content.split("\n"):
            if "Target bins/groups:" in line:
                in_bins = True
                continue
            if in_bins:
                if line.strip().startswith("- `") and "`" in line[3:]:
                    bin_name = line.strip()[3:].split("`")[0]
                    functional_bins.append(bin_name)
                elif line.startswith("###"):
                    break

        # Extract code coverage thresholds
        code_statements = 70.0
        code_branches = 60.0
        code_toggles = 50.0

        stmt_match = re.search(r"Statements:\s*≥(\d+(?:\.\d+)?)%", content)
        if stmt_match:
            code_statements = float(stmt_match.group(1))

        branch_match = re.search(r"Branches:\s*≥(\d+(?:\.\d+)?)%", content)
        if branch_match:
            code_branches = float(branch_match.group(1))

        toggle_match = re.search(r"Toggles:\s*≥(\d+(?:\.\d+)?)%", content)
        if toggle_match:
            code_toggles = float(toggle_match.group(1))

        # Extract health thresholds
        max_uvm_errors = 0
        max_uvm_fatals = 0
        max_scoreboard_errors = 0
        all_assertions_pass = True

        error_match = re.search(r"UVM Errors:\s*≤(\d+)", content)
        if error_match:
            max_uvm_errors = int(error_match.group(1))

        fatal_match = re.search(r"UVM Fatals:\s*≤(\d+)", content)
        if fatal_match:
            max_uvm_fatals = int(fatal_match.group(1))

        scoreboard_match = re.search(r"Scoreboard Errors:\s*≤(\d+)", content)
        if scoreboard_match:
            max_scoreboard_errors = int(scoreboard_match.group(1))

        if "Allow failures" in content:
            all_assertions_pass = False

        # Extract scoring weights
        weights = {
            "functional_coverage": 0.6,
            "code_coverage": 0.3,
            "health": 0.1
        }

        func_weight_match = re.search(r"Functional Coverage:\s*(\d+(?:\.\d+)?)%", content)
        if func_weight_match:
            weights["functional_coverage"] = float(func_weight_match.group(1)) / 100.0

        code_weight_match = re.search(r"Code Coverage:\s*(\d+(?:\.\d+)?)%", content)
        if code_weight_match:
            weights["code_coverage"] = float(code_weight_match.group(1)) / 100.0

        health_weight_match = re.search(r"Health:\s*(\d+(?:\.\d+)?)%", content)
        if health_weight_match:
            weights["health"] = float(health_weight_match.group(1)) / 100.0

        return AcceptanceCriteria(
            functional_bins=functional_bins,
            functional_min_pct=functional_min_pct,
            functional_strategy=functional_strategy,
            code_statements_min_pct=code_statements,
            code_branches_min_pct=code_branches,
            code_toggles_min_pct=code_toggles,
            max_scoreboard_errors=max_scoreboard_errors,
            max_uvm_errors=max_uvm_errors,
            max_uvm_fatals=max_uvm_fatals,
            all_assertions_pass=all_assertions_pass,
            weights=weights
        )


@dataclass
class EvaluationResult:
    """Result of task evaluation."""
    task_id: str
    passed: bool
    score: float
    coverage_report: CoverageReport
    functional_score: float
    code_coverage_score: float
    health_score: float

    # Details
    functional_bins_met: list[str] = field(default_factory=list)
    functional_bins_missed: list[str] = field(default_factory=list)
    thresholds_met: dict[str, bool] = field(default_factory=dict)

    # Artifacts
    log_path: Optional[Path] = None
    coverage_db_path: Optional[Path] = None

    def to_json(self) -> str:
        """Serialize to JSON."""
        data = {
            "task_id": self.task_id,
            "passed": self.passed,
            "score": self.score,
            "functional_score": self.functional_score,
            "code_coverage_score": self.code_coverage_score,
            "health_score": self.health_score,
            "functional_bins_met": self.functional_bins_met,
            "functional_bins_missed": self.functional_bins_missed,
            "thresholds_met": self.thresholds_met,
            "coverage_report": json.loads(self.coverage_report.to_json())
        }
        return json.dumps(data, indent=2)