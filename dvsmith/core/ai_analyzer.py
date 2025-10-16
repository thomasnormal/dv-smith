"""AI-powered repository analyzer using Anthropic Claude."""

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
        prompt = f"""Analyze this UVM verification repository and return a complete RepoAnalysis.

Repository path: {self.repo_root}

Your task:
1. Explore the repository using your tools (Read, Glob, Bash, Grep)
2. Find ALL UVM tests (classes extending uvm_test or names ending with *Test)
3. Find ALL UVM sequences (classes extending uvm_sequence or names ending with *Sequence)
4. Find ALL UVM coverage components (classes extending uvm_subscriber<#(...)> OR uvm_component that define one or more covergroups). Also list any covergroups found (search for 'covergroup').
5. Detect build system (look for Makefile, CMakeLists.txt, FuseSoC *.core, Dvsim *.hjson, etc.)
6. Identify simulators (questa/mentor, xcelium/xrun, vcs, verilator, dsim) referenced in build files or scripts

Notes:
- Search typical locations (test/, tests/, sequences/, seq/, env/, agents/, verification/, tb/) and nested dirs
- Consider both .sv and .svh files
- Return file paths relative to the repo root

Return RepoAnalysis with:
- repo_root: {str(self.repo_root)}
- tests: List[UVMTest] with {name, file_path, base_class, description}
- sequences: List[UVMSequence] with {name, file_path, base_class}
- coverage_components: List[UVMCoverageComponent] with {name, file_path, base_class, covergroups: List[str]}
- covergroups: List[str] in format "ClassName.covergroupName" (if class context unknown, just "covergroupName@relative/path")
- build_system: BuildSystem enum (MAKEFILE, CMAKE, FUSESOC, DVSIM, CUSTOM)
- detected_simulators: List[Simulator] (QUESTA, XCELIUM, VCS, VERILATOR, DSIM)
- tests_dir, sequences_dir, env_dir, agents_dir: Optional paths (relative)

Be thorough—use the tools to explore!
"""

        # Single AI call returns RepoAnalysis directly
        analysis = await query_with_pydantic_response(
            prompt=prompt,
            response_model=RepoAnalysis,
            system_prompt="You are an expert in SystemVerilog/UVM repository analysis. Return complete RepoAnalysis via FinalAnswer.",
            cwd=str(self.repo_root),
            status_cb=status_cb,
            postprocess=lambda obj: self._anchor_paths(obj)
        )

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
        
        return analysis
