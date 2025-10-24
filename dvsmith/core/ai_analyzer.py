"""AI-powered repository analyzer using Anthropic Claude."""

import subprocess
from pathlib import Path
from typing import Optional, Callable

from .ai_structured import query_with_pydantic_response
from .models import RepoAnalysis, BuildSystem, Simulator


class AIRepoAnalyzer:
    """Use Claude to analyze UVM repository structure and extract metadata."""

    def __init__(self, repo_root: Path) -> None:
        """Initialize AI analyzer.

        Args:
            repo_root: Path to repository root
        """
        self.repo_root = Path(repo_root)
        if not self.repo_root.exists():
            raise ValueError(f"Repository not found: {repo_root}")

    async def analyze(self, show_progress: bool = True, status_cb: Optional[Callable] = None) -> RepoAnalysis:
        """Analyze repository using AI (single call).

        Args:
            show_progress: Unused (kept for compatibility)
            status_cb: Optional callback for live status updates

        Returns:
            Complete RepoAnalysis with all discovered elements
        """
        prompt = f"""Analyze this UVM verification repository and return a complete RepoAnalysis with terminal-bench metadata.

Repository path: {self.repo_root}

Your task:
1. Explore the repository using your tools (Read, Glob, Bash, Grep)
2. Find ALL UVM tests (classes extending uvm_test or names ending with *Test)
3. Find ALL UVM sequences (classes extending uvm_sequence or names ending with *Sequence)
4. Find ALL UVM coverage components (classes extending uvm_subscriber<#(...)> OR uvm_component that define one or more covergroups). Also list any covergroups found (search for 'covergroup').
5. Detect build system (look for Makefile, CMakeLists.txt, FuseSoC *.core, Dvsim *.hjson, etc.)
6. Identify simulators (questa/mentor, xcelium/xrun, vcs, verilator, dsim) referenced in build files or scripts
7. Collect SystemVerilog files that primarily contain assertions (interfaces/modules with frequently used SVA constructs like assert property, property/endproperty). Only include files that already exist.
8. Collect files implementing functional coverage (covergroups/coverpoints/crosses) that students might edit.
9. Produce minimal sparse checkout include/exclude glob patterns that expose required sources but hide obvious build artifacts/logs.

Notes:
- Search typical locations (test/, tests/, sequences/, seq/, env/, agents/, verification/, tb/) and nested dirs
- Consider both .sv and .svh files
- Return file paths relative to the repo root

Return RepoAnalysis with:
- repo_root: {str(self.repo_root)}
- tests: List[UVMTest] with [name, file_path, base_class, description]
- sequences: List[UVMSequence] with [name, file_path, base_class]
- coverage_components: List[UVMCoverageComponent] with [name, file_path, base_class]
- build_system: BuildSystem enum (MAKEFILE, CMAKE, FUSESOC, DVSIM, CUSTOM)
- detected_simulators: List[Simulator] (QUESTA, XCELIUM, VCS, VERILATOR, DSIM)
- tests_dir, sequences_dir, env_dir, agents_dir: Optional paths (relative)
- assertion_files: list[str] - relative paths for key assertion sources
- coverage_files: list[str] - relative paths for coverage/covergroup sources
- test_files: list[str] - relative paths for UVM test classes (should align with tests list)
- sparse_include: list[str] - glob patterns for sparse checkout includes
- sparse_exclude: list[str] - glob patterns for sparse checkout excludes

Be thorough—use the tools to explore!
"""

        # Single AI call returns RepoAnalysis directly
        analysis = await query_with_pydantic_response(
            prompt=prompt,
            response_model=RepoAnalysis,
            cwd=str(self.repo_root),
            status_cb=status_cb,
        )
        analysis = self._anchor_paths(analysis)

        analysis.git_commit = analysis.git_commit or self._git("rev-parse", "HEAD")
        analysis.git_remote = analysis.git_remote or self._git("config", "--get", "remote.origin.url")
        analysis.git_branch = analysis.git_branch or self._git("symbolic-ref", "--short", "HEAD")

        if not analysis.test_files:
            analysis.test_files = [t.file_path for t in analysis.tests]
        if not analysis.assertion_files:
            analysis.assertion_files = self._guess_assertion_files()
        if not analysis.coverage_files:
            analysis.coverage_files = [Path(comp.file_path) for comp in analysis.coverage_components]

        self._finalize_sparse_patterns(analysis)

        return analysis

    def _anchor_paths(self, analysis: RepoAnalysis) -> RepoAnalysis:
        """Anchor relative paths to absolute paths.
        
        Args:
            analysis: RepoAnalysis with potentially relative paths
            
        Returns:
            RepoAnalysis with absolute paths
        """
        # Ensure repo_root is set
        analysis.repo_root = self.repo_root
        
        # Anchor directory paths
        if analysis.tests_dir and not analysis.tests_dir.is_absolute():
            analysis.tests_dir = self.repo_root / analysis.tests_dir
        if analysis.sequences_dir and not analysis.sequences_dir.is_absolute():
            analysis.sequences_dir = self.repo_root / analysis.sequences_dir
        if analysis.env_dir and not analysis.env_dir.is_absolute():
            analysis.env_dir = self.repo_root / analysis.env_dir
        if analysis.agents_dir and not analysis.agents_dir.is_absolute():
            analysis.agents_dir = self.repo_root / analysis.agents_dir
        
        # Anchor test file paths
        for test in analysis.tests:
            if not test.file_path.is_absolute():
                test.file_path = self.repo_root / test.file_path
        
        # Anchor sequence file paths
        for seq in analysis.sequences:
            if not seq.file_path.is_absolute():
                seq.file_path = self.repo_root / seq.file_path

        for component in analysis.coverage_components:
            if not component.file_path.is_absolute():
                component.file_path = self.repo_root / component.file_path

        analysis.assertion_files = self._dedupe_paths(
            [self._anchor_path(p) for p in analysis.assertion_files]
        )
        analysis.coverage_files = self._dedupe_paths(
            [self._anchor_path(p) for p in analysis.coverage_files]
        )
        analysis.test_files = self._dedupe_paths(
            [self._anchor_path(p) for p in analysis.test_files]
        )

        if not analysis.covergroups:
            analysis.covergroups = analysis._derived_covergroups()
        
        return analysis

    def _anchor_path(self, path: Path | str) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.repo_root / candidate

    def _git(self, *args: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def _guess_assertion_files(self) -> list[Path]:
        assertion_paths: list[Path] = []
        for component in self.repo_root.rglob("*.sv"):
            name_lower = component.name.lower()
            if "assert" in name_lower or "sva" in name_lower:
                assertion_paths.append(component)
        return assertion_paths[:10]

    def _finalize_sparse_patterns(self, analysis: RepoAnalysis) -> None:
        if analysis.sparse_include and analysis.sparse_exclude:
            return

        include: set[str] = set(analysis.sparse_include)
        exclude: set[str] = set(analysis.sparse_exclude)

        def add_parent_globs(paths: list[Path]) -> None:
            for path in paths:
                try:
                    rel = path.relative_to(self.repo_root)
                except ValueError:
                    rel = path
                parts = rel.parts
                if parts:
                    include.add(str(Path(parts[0]) / "**"))

        add_parent_globs(analysis.test_files)
        add_parent_globs(analysis.assertion_files)
        add_parent_globs(analysis.coverage_files)

        if not include:
            include.add("**")

        if not exclude:
            exclude.update({"build/**", "out/**", "logs/**", "**/.git/**", "**/.cache/**"})

        analysis.sparse_include = sorted(include)
        analysis.sparse_exclude = sorted(exclude)

    def _dedupe_paths(self, paths: list[Path]) -> list[Path]:
        seen: list[Path] = []
        for path in paths:
            if path not in seen:
                seen.append(path)
        return seen
