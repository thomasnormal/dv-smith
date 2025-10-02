"""Repository analyzer for discovering UVM tests, sequences, and covergroups."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import BuildSystem, RepoAnalysis, Simulator, UVMSequence, UVMTest


@dataclass
class AnalyzerHints:
    """User-provided hints to guide analysis."""
    tests_dir: Optional[Path] = None
    sequences_dir: Optional[Path] = None
    env_dir: Optional[Path] = None
    build_dir: Optional[Path] = None
    known_simulators: Optional[list[Simulator]] = None
    build_system: Optional[BuildSystem] = None


class RepoAnalyzer:
    """Analyze SV/UVM repository to extract structure and metadata.

    Three-stage analysis:
    1. Static parsing (SV source analysis)
    2. Heuristic detection (build systems, simulators)
    3. Agent refinement (try compile, fill gaps)
    """

    def __init__(self, repo_root: Path) -> None:
        """Initialize analyzer.

        Args:
            repo_root: Path to repository root
        """
        self.repo_root = Path(repo_root)
        if not self.repo_root.exists():
            raise ValueError(f"Repository not found: {repo_root}")

    def analyze_static(self, hints: Optional[AnalyzerHints] = None) -> RepoAnalysis:
        """Stage 1: Static analysis using SV source parsing.

        Args:
            hints: Optional user hints to guide discovery

        Returns:
            RepoAnalysis with discovered tests, sequences, covergroups
        """
        hints = hints or AnalyzerHints()
        analysis = RepoAnalysis(repo_root=self.repo_root)

        # Discover directory structure
        analysis.tests_dir = self._find_tests_dir(hints)
        analysis.sequences_dir = self._find_sequences_dir(hints)
        analysis.env_dir = self._find_env_dir(hints)
        analysis.agents_dir = self._find_agents_dir(hints)

        # Parse SV files for UVM constructs
        if analysis.tests_dir:
            analysis.tests = self._parse_uvm_tests(analysis.tests_dir)

        if analysis.sequences_dir:
            analysis.sequences = self._parse_uvm_sequences(analysis.sequences_dir)

        # Find covergroups across all SV files
        analysis.covergroups = self._find_covergroups()

        return analysis

    def detect_build_system(self, analysis: RepoAnalysis,
                           hints: Optional[AnalyzerHints] = None) -> RepoAnalysis:
        """Stage 2: Detect build system and simulators heuristically.

        Args:
            analysis: Initial analysis from static stage
            hints: Optional user hints

        Returns:
            Updated RepoAnalysis with build system info
        """
        hints = hints or AnalyzerHints()

        # Detect build system
        if hints.build_system:
            analysis.build_system = hints.build_system
        else:
            analysis.build_system = self._detect_build_system()

        # Detect simulators from build files
        if hints.known_simulators:
            analysis.detected_simulators = hints.known_simulators
        else:
            analysis.detected_simulators = self._detect_simulators()

        return analysis

    def refine_with_agent(self, analysis: RepoAnalysis) -> RepoAnalysis:
        """Stage 3: Use LLM agent to refine and validate analysis.

        This would use an agent (like SWE-agent) to:
        - Try compiling with detected build system
        - Fix common path/include issues
        - Validate smoke tests run
        - Fill in missing profile fields

        Args:
            analysis: Analysis from previous stages

        Returns:
            Refined RepoAnalysis

        Note:
            This is a placeholder. Full implementation would integrate
            with SWE-agent or similar tool.
        """
        # TODO: Implement agent integration
        # - Spawn agent in container
        # - Ask it to try compile
        # - Capture any fixes/insights
        # - Update analysis accordingly
        return analysis

    # === Private helper methods ===

    def _find_tests_dir(self, hints: AnalyzerHints) -> Optional[Path]:
        """Find directory containing UVM tests."""
        if hints.tests_dir and hints.tests_dir.exists():
            return hints.tests_dir

        # Common patterns for test directories (check most specific first)
        candidates = [
            "test", "tests",
            "tb/test", "tb/tests",
            "hvl_top/test", "src/hvl_top/test",
            "hvlTop/tb/test", "src/hvlTop/tb/test",  # PascalCase variants
            "HvlTop/tb/test", "src/HvlTop/tb/test",
            "verif/test", "verification/test",
            "testbench/test", "testbench/tests"
        ]

        for candidate in candidates:
            path = self.repo_root / candidate
            if path.exists() and path.is_dir():
                # Check if it contains .sv files with test classes
                sv_files = list(path.glob("*.sv")) + list(path.glob("**/*.sv"))
                if sv_files:
                    # Quick check if any file has "extends" and "test"
                    for sv_file in sv_files[:5]:  # Sample first 5 files
                        try:
                            content = sv_file.read_text()
                            if re.search(r"class\s+\w+\s+extends\s+\w*[Tt]est", content):
                                return path
                        except:
                            pass
                    # If contains .sv files but no test classes found in sample, continue
                    # But keep as fallback
                    if list(path.glob("*.sv")):
                        return path

        return None

    def _find_sequences_dir(self, hints: AnalyzerHints) -> Optional[Path]:
        """Find directory containing UVM sequences."""
        if hints.sequences_dir and hints.sequences_dir.exists():
            return hints.sequences_dir

        candidates = [
            "sequences", "seq", "tb/sequences", "tb/seq",
            "hvl_top/sequences", "src/hvl_top/sequences",
            "verif/sequences"
        ]

        for candidate in candidates:
            path = self.repo_root / candidate
            if path.exists() and path.is_dir():
                if list(path.glob("*.sv")) or list(path.glob("**/*.sv")):
                    return path

        return None

    def _find_env_dir(self, hints: AnalyzerHints) -> Optional[Path]:
        """Find environment directory."""
        if hints.env_dir and hints.env_dir.exists():
            return hints.env_dir

        candidates = [
            "env", "tb/env", "hvl_top/env", "src/hvl_top/env",
            "verif/env", "verification/env"
        ]

        for candidate in candidates:
            path = self.repo_root / candidate
            if path.exists() and path.is_dir():
                return path

        return None

    def _find_agents_dir(self, hints: AnalyzerHints) -> Optional[Path]:
        """Find agents directory."""
        candidates = [
            "agents", "agent", "tb/agents", "hvl_top/agents",
            "src/hvl_top/agents", "verif/agents"
        ]

        for candidate in candidates:
            path = self.repo_root / candidate
            if path.exists() and path.is_dir():
                return path

        return None

    def _parse_uvm_tests(self, tests_dir: Path) -> list[UVMTest]:
        """Parse UVM test classes from SV files.

        Looks for patterns like:
            class <name> extends <base>;
        where base contains "test" or inherits from uvm_test.
        """
        tests = []
        sv_files = list(tests_dir.glob("**/*.sv")) + list(tests_dir.glob("**/*.svh"))

        for sv_file in sv_files:
            try:
                content = sv_file.read_text()
                tests.extend(self._extract_tests_from_content(sv_file, content))
            except Exception as e:
                print(f"Warning: Could not parse {sv_file}: {e}")

        return tests

    def _extract_tests_from_content(self, file_path: Path, content: str) -> list[UVMTest]:
        """Extract test classes from file content."""
        tests = []

        # Pattern: class <name> extends <base_class>
        # Look for base classes containing "test" or common UVM test bases
        class_pattern = re.compile(
            r"class\s+(\w+)\s+extends\s+(\w+)",
            re.MULTILINE
        )

        for match in class_pattern.finditer(content):
            class_name = match.group(1)
            base_class = match.group(2)

            # Filter for test-like classes
            if "test" in base_class.lower() or base_class in ["uvm_test"]:
                # Try to find description from comments
                description = self._extract_description(content, match.start())

                tests.append(UVMTest(
                    name=class_name,
                    file_path=file_path,
                    base_class=base_class,
                    description=description,
                    line_number=content[:match.start()].count("\n") + 1
                ))

        return tests

    def _parse_uvm_sequences(self, sequences_dir: Path) -> list[UVMSequence]:
        """Parse UVM sequence classes from SV files."""
        sequences = []
        sv_files = list(sequences_dir.glob("**/*.sv")) + list(sequences_dir.glob("**/*.svh"))

        for sv_file in sv_files:
            try:
                content = sv_file.read_text()
                sequences.extend(self._extract_sequences_from_content(sv_file, content))
            except Exception as e:
                print(f"Warning: Could not parse {sv_file}: {e}")

        return sequences

    def _extract_sequences_from_content(self, file_path: Path,
                                       content: str) -> list[UVMSequence]:
        """Extract sequence classes from file content."""
        sequences = []

        class_pattern = re.compile(
            r"class\s+(\w+)\s+extends\s+(\w+)",
            re.MULTILINE
        )

        for match in class_pattern.finditer(content):
            class_name = match.group(1)
            base_class = match.group(2)

            # Filter for sequence-like classes
            if "seq" in base_class.lower() or base_class in ["uvm_sequence"]:
                description = self._extract_description(content, match.start())

                sequences.append(UVMSequence(
                    name=class_name,
                    file_path=file_path,
                    base_class=base_class,
                    description=description,
                    line_number=content[:match.start()].count("\n") + 1
                ))

        return sequences

    def _find_covergroups(self) -> list[str]:
        """Find all covergroup definitions in repository.

        Returns list of fully qualified covergroup names.
        """
        covergroups = []
        sv_files = list(self.repo_root.glob("**/*.sv")) + list(self.repo_root.glob("**/*.svh"))

        covergroup_pattern = re.compile(
            r"covergroup\s+(\w+)",
            re.MULTILINE
        )

        for sv_file in sv_files:
            try:
                content = sv_file.read_text()
                for match in covergroup_pattern.finditer(content):
                    cg_name = match.group(1)
                    # Try to find class context for fully qualified name
                    class_name = self._find_enclosing_class(content, match.start())
                    full_name = f"{class_name}.{cg_name}" if class_name else cg_name
                    covergroups.append(full_name)
            except Exception as e:
                print(f"Warning: Could not parse {sv_file}: {e}")

        return covergroups

    def _find_enclosing_class(self, content: str, position: int) -> Optional[str]:
        """Find the class name enclosing a given position in content."""
        # Look backward for class declaration
        before = content[:position]
        class_pattern = re.compile(r"class\s+(\w+)\s+extends\s+\w+")
        matches = list(class_pattern.finditer(before))
        if matches:
            return matches[-1].group(1)
        return None

    def _extract_description(self, content: str, position: int) -> Optional[str]:
        """Extract description from comments before a construct."""
        before = content[:position]
        lines = before.split("\n")

        # Look for comment lines immediately before (within 5 lines)
        desc_lines = []
        for line in reversed(lines[-5:]):
            stripped = line.strip()
            if stripped.startswith("//"):
                desc_lines.insert(0, stripped[2:].strip())
            elif stripped.startswith("/*") or stripped.endswith("*/"):
                # Handle block comments (simplified)
                desc_lines.insert(0, stripped.strip("/* "))
            elif stripped == "":
                continue
            else:
                break

        return " ".join(desc_lines) if desc_lines else None

    def _detect_build_system(self) -> Optional[BuildSystem]:
        """Detect build system from repository structure."""
        # Check for specific build files
        if (self.repo_root / "Makefile").exists():
            return BuildSystem.MAKEFILE

        if (self.repo_root / "CMakeLists.txt").exists():
            return BuildSystem.CMAKE

        # Look for dvsim (OpenTitan-style)
        if list(self.repo_root.glob("**/dvsim.py")):
            return BuildSystem.DVSIM

        # Look for fusesoc
        if (self.repo_root / "fusesoc.conf").exists() or \
           list(self.repo_root.glob("**/*.core")):
            return BuildSystem.FUSESOC

        return BuildSystem.CUSTOM

    def _detect_simulators(self) -> list[Simulator]:
        """Detect simulators from build files and scripts."""
        detected = set()

        # Search in common build files (case-insensitive)
        search_files = []

        # Find all Makefiles (case-insensitive)
        for pattern in ["Makefile", "makefile", "MAKEFILE"]:
            search_files.extend(self.repo_root.glob(f"**/{pattern}"))

        # Add all .mk, .sh files
        search_files.extend(self.repo_root.glob("**/*.mk"))
        search_files.extend(self.repo_root.glob("**/*.sh"))

        # Simulator tool patterns
        patterns = {
            Simulator.QUESTA: [r"\bvsim\b", r"\bquesta\b", r"\bmodelsim\b"],
            Simulator.XCELIUM: [r"\bxrun\b", r"\birun\b", r"\bxcelium\b", r"\bncsim\b"],
            Simulator.VCS: [r"\bvcs\b", r"\bsimv\b", r"\burg\b"],
            Simulator.VERILATOR: [r"\bverilator\b"],
            Simulator.DSIM: [r"\bdsim\b"],
        }

        for file_path in search_files:
            if not file_path.exists() or not file_path.is_file():
                continue

            try:
                content = file_path.read_text()
                for sim, sim_patterns in patterns.items():
                    for pattern in sim_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            detected.add(sim)
            except Exception:
                pass

        return list(detected)