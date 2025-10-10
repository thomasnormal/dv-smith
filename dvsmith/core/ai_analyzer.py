"""AI-powered repository analyzer using Anthropic Claude."""

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from tqdm import tqdm

from .ai_structured import query_with_pydantic_response
from .ai_models import DirectoryInfo, FilesEnvelope, TestInfo, BuildInfo
from .models import BuildSystem, RepoAnalysis, Simulator, UVMSequence, UVMTest


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

    def analyze(self) -> RepoAnalysis:
        """Analyze repository using AI.

        Returns:
            Complete RepoAnalysis with all discovered elements
        """
        # Create progress bar for analysis steps
        with tqdm(total=6, desc="AI Analysis", unit="step", position=1, leave=False) as pbar:
            # Step 1: Get directory tree and file list
            pbar.set_description("Gathering file tree")
            file_tree = self._get_file_tree()
            pbar.update(1)

            # Step 2: Use AI to identify key directories
            pbar.set_description("Identifying directories")
            dir_info = self._identify_directories(file_tree)
            pbar.update(1)

            # Step 3: Extract test files and analyze them
            pbar.set_description("Analyzing tests")
            tests = self._analyze_tests(dir_info.tests_dir)
            pbar.update(1)

            # Step 4: Extract sequence files
            pbar.set_description("Analyzing sequences")
            sequences = self._analyze_sequences(dir_info.sequences_dir)
            pbar.update(1)

            # Step 5: Find covergroups
            pbar.set_description("Finding covergroups")
            covergroups = self._find_covergroups(dir_info)
            pbar.update(1)

            # Step 6: Detect build system and simulators
            pbar.set_description("Detecting build system")
            build_info = self._detect_build_system()
            pbar.update(1)

            # Construct analysis
            analysis = RepoAnalysis(
                repo_root=self.repo_root,
                tests=tests,
                sequences=sequences,
                covergroups=covergroups,
                build_system=build_info.get("build_system"),
                detected_simulators=build_info.get("simulators", [])
            )

        # Set directory paths
        if dir_info.tests_dir:
            analysis.tests_dir = self.repo_root / dir_info.tests_dir
        if dir_info.sequences_dir:
            analysis.sequences_dir = self.repo_root / dir_info.sequences_dir
        if dir_info.env_dir:
            analysis.env_dir = self.repo_root / dir_info.env_dir
        if dir_info.agents_dir:
            analysis.agents_dir = self.repo_root / dir_info.agents_dir

        return analysis

    def _get_file_tree(self) -> str:
        """Get repository file tree structure.

        Returns:
            Tree structure as string
        """
        try:
            # Use tree command if available, otherwise use find
            result = subprocess.run(
                ["tree", "-L", "4", "-I", ".git|work|*.log|*.ucdb", str(self.repo_root)],
                capture_output=True,
                text=True,
                timeout=10  # Reduced from 30s
            )
            if result.returncode == 0:
                return result.stdout
        except:
            pass

        # Fallback: use find
        try:
            result = subprocess.run(
                ["find", str(self.repo_root), "-type", "f", "-name", "*.sv"],
                capture_output=True,
                text=True,
                timeout=15  # Reduced from 30s
            )
            return result.stdout
        except:
            # Last resort: Python walk with safety cap
            files = []
            for i, path in enumerate(self.repo_root.rglob("*.sv")):
                if i >= 2000:  # Safety cap
                    break
                try:
                    rel_path = path.relative_to(self.repo_root)
                    files.append(str(rel_path))
                except:
                    pass
            return "\n".join(files[:100])  # Limit to first 100

    def _identify_directories(self, file_tree: str) -> DirectoryInfo:
        """Use AI to identify key directories.

        Args:
            file_tree: Repository structure

        Returns:
            Dictionary with directory paths
        """
        # Get list of directories with test/Test in name AND identify test files by content
        test_dir_candidates = []
        dirs_checked = 0
        for path in self.repo_root.rglob("*"):
            if path.is_dir() and ("test" in path.name.lower() or "Test" in path.name):
                dirs_checked += 1
                if dirs_checked > 50:  # Safety cap on directory checking
                    break
                try:
                    rel = path.relative_to(self.repo_root)
                    sv_files = list(path.rglob("*.sv"))[:200]  # Cap files per dir

                    if not sv_files:
                        continue

                    # Identify test files by content analysis (not filename pattern)
                    test_files = []
                    for sv_file in sv_files:
                        try:
                            # Read first 3000 chars to check for test class indicators
                            # (handles files with long license headers)
                            content = sv_file.read_text(encoding='utf-8', errors='ignore')[:3000]
                            content_lower = content.lower()

                            # Check for UVM test class patterns (tighter check)
                            has_class_extends = bool(re.search(r"class\s+\w+\s+extends\s+([a-zA-Z_][\w:#]*)", content, re.I))
                            is_test = has_class_extends and (
                                "uvm_test" in content_lower or
                                bool(re.search(r"extends\s+\w*_test\b", content, re.I))
                            )

                            if is_test:
                                test_files.append(sv_file)
                        except:
                            # If can't read file, skip it
                            pass

                    if test_files:
                        # Sample files and count
                        samples = [f.name for f in test_files[:3]]
                        priority = "HIGH" if "src" in str(rel) or "hvl" in str(rel) else "LOW"
                        test_dir_candidates.append({
                            "path": str(rel),
                            "count": len(test_files),
                            "samples": samples,
                            "priority": priority
                        })

                        # Short-circuit if we have enough good candidates
                        if len(test_dir_candidates) >= 10:
                            break
                except:
                    pass

        # Sort by priority (HIGH first) then by count (most tests first)
        test_dir_candidates.sort(key=lambda x: (x["priority"] == "LOW", -x["count"]))

        # If we found exactly one test directory, use it directly (no need for AI to choose)
        if len(test_dir_candidates) == 1:
            tqdm.write(f"[AI Analyzer] Found single test directory: {test_dir_candidates[0]['path']}")
            return DirectoryInfo(
                tests_dir=test_dir_candidates[0]['path'],
                sequences_dir=None,
                env_dir=None,
                agents_dir=None
            )

        # Call async version
        return asyncio.run(self._identify_directories_async(file_tree, test_dir_candidates))

    async def _identify_directories_async(self, file_tree: str, test_dir_candidates: list[dict]) -> DirectoryInfo:
        """Use AI to identify key directories (async).

        Args:
            file_tree: Repository structure
            test_dir_candidates: Pre-computed test directory candidates

        Returns:
            Dictionary with directory paths
        """
        # Format for prompt
        test_dir_info = []
        for c in test_dir_candidates[:10]:
            test_dir_info.append(f"{c['path']} [{c['priority']} priority, {c['count']} tests: {', '.join(c['samples'])}]")

        prompt = f"""Analyze this SystemVerilog/UVM repository and identify the COMPLETE EXACT directory paths.

Test directory candidates (sorted by priority and test count):
{chr(10).join(test_dir_info) if test_dir_info else "No test directories found"}

Based on the test directory candidates above, identify:
1. tests_dir: Choose the BEST directory for integration tests (UVM test classes)
   - PREFER directories marked [HIGH priority] - these are typically in src/hvl_top/test or similar
   - AVOID unit_test/* paths - these are for component unit tests, not integration tests
   - Pick the directory with the MOST test files if multiple HIGH priority directories exist

2. sequences_dir: Directory with sequence files (look for *_seq.sv or *_sequence.sv)
3. env_dir: Directory with environment files (look for *_env.sv)
4. agents_dir: Directory with agent files (look for *_agent.sv)

CRITICAL RULES:
- Use the EXACT path from the "Test directory candidates" list above
- For tests_dir, ALWAYS prefer [HIGH priority] over [LOW priority]
- Use null for any directory not found
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=DirectoryInfo,
                system_prompt="You are an expert in SystemVerilog and UVM testbench structure.",
                cwd=str(self.repo_root)
            )

            # Validate that the tests_dir actually exists
            if result.tests_dir:
                test_path = self.repo_root / result.tests_dir
                if not test_path.exists():
                    tqdm.write(f"[AI Analyzer] Warning: AI suggested non-existent path: {result.tests_dir}")
                    # Use first candidate we actually found
                    if test_dir_candidates:
                        tqdm.write(f"[AI Analyzer] Using first discovered directory instead: {test_dir_candidates[0]['path']}")
                        result.tests_dir = test_dir_candidates[0]['path']
                    else:
                        result.tests_dir = None

            return result

        except Exception as e:
            tqdm.write(f"[AI Analyzer] Warning: Could not parse directory info: {e}")
            # Fallback to first candidate if available
            if test_dir_candidates:
                tqdm.write(f"[AI Analyzer] Using first discovered directory as fallback: {test_dir_candidates[0]['path']}")
                return DirectoryInfo(
                    tests_dir=test_dir_candidates[0]['path'],
                    sequences_dir=None,
                    env_dir=None,
                    agents_dir=None
                )
            return DirectoryInfo(tests_dir=None, sequences_dir=None, env_dir=None, agents_dir=None)

    def _analyze_tests(self, tests_dir: Optional[str]) -> list[UVMTest]:
        """Analyze test files using AI.

        Args:
            tests_dir: Tests directory path

        Returns:
            List of discovered UVMTest objects
        """
        if not tests_dir:
            return []

        tests_path = self.repo_root / tests_dir
        if not tests_path.exists():
            return []

        # Get full directory tree for AI to analyze
        try:
            result = subprocess.run(
                ["ls", "-R", str(tests_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            dir_tree = result.stdout[:2000]  # First 2k chars of tree
        except:
            dir_tree = f"Directory: {tests_dir}"

        # Ask AI to identify test files from directory structure
        test_file_paths = self._find_test_files_with_ai(tests_path, dir_tree)

        tests = []

        # Analyze each identified test file with AI
        for test_file in tqdm(test_file_paths[:100], desc="Analyzing tests", unit="file"):
            try:
                content = test_file.read_text()[:5000]  # First 5k chars

                # Quick check if it contains a test class
                if "extends" not in content or "class" not in content:
                    continue

                test_info = self._extract_test_info(test_file, content)
                if test_info:
                    tests.append(test_info)
            except Exception as e:
                tqdm.write(f"[AI Analyzer] Warning: Could not analyze {test_file.name}: {e}")

        return tests

    def _find_test_files_with_ai(self, tests_path: Path, dir_tree: str) -> list[Path]:
        """Use AI to identify test files from directory tree.

        Args:
            tests_path: Path to test directory
            dir_tree: Output of ls -R

        Returns:
            List of Path objects to test files
        """
        return asyncio.run(self._find_test_files_with_ai_async(tests_path, dir_tree))

    async def _find_test_files_with_ai_async(self, tests_path: Path, dir_tree: str) -> list[Path]:
        """Use AI to identify test files from directory tree (async).

        Args:
            tests_path: Path to test directory
            dir_tree: Output of ls -R

        Returns:
            List of Path objects to test files
        """
        prompt = f"""Analyze this UVM test directory structure and identify ALL test class files.

Directory tree:
```
{dir_tree}
```

IMPORTANT:
- Include ANY .sv files that might contain UVM test classes
- Test files can have ANY naming convention (PascalCase, snake_case, etc.):
  - Examples: SpiDualSpiTypeTest.sv, apb_8b_write_test.sv, my_test_case.sv
- EXCLUDE sequence files (contain "seq" or "sequence" in name or path)
- EXCLUDE package files (*pkg.sv, *package*.sv)
- EXCLUDE files in "sequences" or "seq" directories
- When in doubt, include the file (we verify contents later)

Return format (STRICT):
- Call the FinalAnswer tool with a JSON OBJECT of the exact shape:
  {{"kind": "dvsmith.files.v1", "files": ["apb_8b_write_test.sv", "apb_16b_read_test.sv"]}}
- Do NOT include any other properties.
- The "kind" field must be exactly "dvsmith.files.v1".
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=FilesEnvelope,
                system_prompt="You are an expert in UVM directory structures.",
                cwd=str(tests_path.resolve())
            )

            file_paths = result.files
            tqdm.write(f"[AI Analyzer] AI identified {len(file_paths)} test files")
            # Don't print individual files to keep progress bar clean

            # Convert to Path objects
            paths = []
            for fpath in file_paths:
                # Handle both absolute and relative paths
                p = Path(fpath)

                if p.is_absolute():
                    full_path = p
                else:
                    # AI returns paths relative to CWD, which may include workspace prefix
                    # Strip any leading workspace/clone prefix to get just the relative path
                    full_path = None

                    # Try interpreting as relative to CWD first
                    cwd_path = Path.cwd() / fpath
                    if cwd_path.exists():
                        full_path = cwd_path
                    else:
                        # Try relative to tests_path (strip common prefixes)
                        fpath_str = str(fpath)
                        # Remove workspace prefix if present
                        for prefix in ["dvsmith_workspace/clones/", "workspace/clones/", str(self.repo_root.name) + "/"]:
                            if fpath_str.startswith(prefix):
                                fpath_str = fpath_str[len(prefix):]
                                break

                        # Try with just the filename relative to tests_path
                        just_filename = Path(fpath).name
                        candidate = tests_path / just_filename
                        if candidate.exists():
                            full_path = candidate
                        else:
                            # Try the stripped path relative to tests_path
                            candidate = tests_path / fpath_str
                            if candidate.exists():
                                full_path = candidate

                if full_path and full_path.exists():
                    paths.append(full_path)
                else:
                    tqdm.write(f"[AI Analyzer] Warning: File not found: {fpath}")

            # If AI returned empty list or no valid files, raise error
            if not paths:
                raise RuntimeError(f"AI did not identify any valid test files in {tests_path}")

            return paths

        except Exception as e:
            raise RuntimeError(f"Could not identify test files with AI: {e}") from e

    def _extract_test_info(self, file_path: Path, content: str) -> Optional[UVMTest]:
        """Extract test information using local parsing first, AI as fallback.

        Args:
            file_path: Path to test file
            content: File content

        Returns:
            UVMTest object or None
        """
        # Fast local path: find a class that looks like a test
        m = re.search(r"class\s+(\w+)\s+extends\s+([a-zA-Z_][\w:#]*)", content)
        if m:
            cls, base = m.group(1), m.group(2)
            base_l = base.lower()
            # Check if it's a test (not a sequence)
            if "sequence" not in base_l and ("uvm_test" in base_l or base_l.endswith("_test")):
                # Try to grab a simple description from file or comments
                desc = self._guess_description(content, cls) or f"Test class {cls}"
                return UVMTest(
                    name=cls,
                    file_path=file_path,
                    base_class=base.split("#")[0],  # Strip parameterization
                    description=desc,
                )

        # If local parsing didn't work, skip AI for now (too slow)
        # Can fall back to AI later if needed
        return None

    def _guess_description(self, content: str, cls: str) -> Optional[str]:
        """Extract description from comments near the class definition.

        Args:
            content: File content
            cls: Class name

        Returns:
            Description string or None
        """
        # Grab comments immediately above the class
        m = re.search(r"(?:\/\/[^\n]*\n){0,3}\s*class\s+" + re.escape(cls) + r"\b", content)
        if not m:
            return None
        snippet = content[max(0, m.start()-300):m.start()]
        cm = re.findall(r"\/\/\s*(.+)", snippet)
        return cm[-1].strip() if cm else None

    async def _extract_test_info_async(self, file_path: Path, content: str) -> Optional[UVMTest]:
        """Extract test information using AI (async).

        Args:
            file_path: Path to test file
            content: File content

        Returns:
            UVMTest object or None
        """
        prompt = f"""Analyze this SystemVerilog file and determine if it contains a UVM TEST class.

File: {file_path.name}
```systemverilog
{content}
```

IMPORTANT: This should ONLY be classified as a UVM test if it:
- Contains a class that extends uvm_test or a *_test base class
- Is NOT a sequence (extends *_sequence or uvm_sequence)
- Is NOT a package file (*_pkg.sv)
- Is NOT a configuration class
- Is NOT a virtual sequence

If this IS a valid UVM test class, extract:
1. class_name: Name of the TEST class
2. base_class: What it extends
3. description: Brief description (1 sentence) of what it tests
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=TestInfo,
                system_prompt="You are an expert in SystemVerilog/UVM.",
                cwd=str(self.repo_root)
            )

            if not result.is_test or not result.class_name:
                return None

            return UVMTest(
                name=result.class_name,
                file_path=file_path,
                base_class=result.base_class or "unknown",
                description=result.description
            )

        except Exception as e:
            tqdm.write(f"[AI Analyzer] ERROR: Failed to extract test from {file_path.name}: {e}")
            return None

    def _analyze_sequences(self, sequences_dir: Optional[str]) -> list[UVMSequence]:
        """Analyze sequence files.

        Args:
            sequences_dir: Sequences directory path

        Returns:
            List of discovered UVMSequence objects
        """
        if not sequences_dir:
            return []

        seq_path = self.repo_root / sequences_dir
        if not seq_path.exists():
            return []

        seq_files = list(seq_path.glob("**/*.sv"))
        sequences = []

        for seq_file in seq_files[:50]:
            try:
                content = seq_file.read_text()[:5000]

                if "extends" not in content or "class" not in content:
                    continue

                # Simple regex extraction for sequences (handle parameterized bases)
                match = re.search(r"class\s+(\w+)\s+extends\s+([a-zA-Z_][\w:#]*)", content)
                if match and ("seq" in match.group(2).lower() or "uvm_sequence" in match.group(2).lower()):
                    base_class = match.group(2).split("#")[0]  # Strip parameterization
                    sequences.append(UVMSequence(
                        name=match.group(1),
                        file_path=seq_file,
                        base_class=base_class
                    ))
            except Exception:
                continue

        return sequences

    def _find_covergroups(self, dir_info: DirectoryInfo) -> list[str]:
        """Find covergroup definitions using AI.

        Args:
            dir_info: Directory information

        Returns:
            List of covergroup names
        """
        # Search in env and agents directories
        search_dirs = []
        for dir_path in [dir_info.env_dir, dir_info.agents_dir]:
            if dir_path:
                path = self.repo_root / dir_path
                if path.exists():
                    search_dirs.append(path)

        if not search_dirs:
            search_dirs = [self.repo_root / "src"]

        covergroups = []
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for sv_file in list(search_dir.glob("**/*.sv"))[:30]:
                try:
                    content = sv_file.read_text()
                    import re
                    matches = re.findall(r"covergroup\s+(\w+)", content)
                    for cg_name in matches:
                        # Try to find enclosing class
                        class_match = re.search(
                            rf"class\s+(\w+).*?covergroup\s+{cg_name}",
                            content,
                            re.DOTALL
                        )
                        if class_match:
                            full_name = f"{class_match.group(1)}.{cg_name}"
                        else:
                            full_name = cg_name

                        if full_name not in covergroups:
                            covergroups.append(full_name)
                except:
                    continue

        return covergroups[:20]  # Limit to 20

    def _detect_build_system(self) -> dict[str, Any]:
        """Detect build system and simulators using AI + regex fallback.

        Returns:
            Dictionary with build_system and simulators
        """
        # Find build files
        build_files = []
        for pattern in ["Makefile", "makefile", "*.mk", "*.f", "compile.f"]:
            build_files.extend(list(self.repo_root.glob(f"**/{pattern}"))[:5])

        if not build_files:
            return {"build_system": BuildSystem.CUSTOM, "simulators": []}

        # Read build files and do regex detection as fallback
        build_content = ""
        detected_sims = set()

        for bf in build_files[:5]:
            try:
                content = bf.read_text()[:3000]
                build_content += f"\n--- {bf.name} ---\n{content}\n"

                # Regex fallback for simulators
                if re.search(r"\b(vsim|questa|modelsim)\b", content, re.IGNORECASE):
                    detected_sims.add("questa")
                if re.search(r"\b(xrun|irun|xcelium|ncsim)\b", content, re.IGNORECASE):
                    detected_sims.add("xcelium")
                if re.search(r"\b(vcs|simv)\b", content, re.IGNORECASE):
                    detected_sims.add("vcs")
                if re.search(r"\bverilator\b", content, re.IGNORECASE):
                    detected_sims.add("verilator")
                if re.search(r"\bdsim\b", content, re.IGNORECASE):
                    detected_sims.add("dsim")
            except:
                pass

        # Call async version
        return asyncio.run(self._detect_build_system_async(build_content, detected_sims))

    async def _detect_build_system_async(self, build_content: str, detected_sims: set[str]) -> dict[str, Any]:
        """Detect build system and simulators using AI (async).

        Args:
            build_content: Concatenated build file contents
            detected_sims: Simulators detected by regex

        Returns:
            Dictionary with build_system and simulators
        """
        prompt = f"""Analyze these build files and identify:
1. Build system type (makefile, cmake, fusesoc, dvsim, or custom)
2. ALL simulators mentioned or supported (questa, modelsim, xcelium, irun, vcs, verilator, dsim)

Build files:
```
{build_content[:4000]}
```

Look for:
- Tool commands: vsim, xrun, irun, vcs, verilator, dsim
- Directory names: questa_sim, cadence_sim, synopsys_sim
- Comments mentioning simulators
"""

        # Define mappings outside try block so they're available in except
        build_sys_map = {
            "makefile": BuildSystem.MAKEFILE,
            "cmake": BuildSystem.CMAKE,
            "fusesoc": BuildSystem.FUSESOC,
            "dvsim": BuildSystem.DVSIM,
            "custom": BuildSystem.CUSTOM
        }

        sim_map = {
            "questa": Simulator.QUESTA,
            "modelsim": Simulator.QUESTA,
            "xcelium": Simulator.XCELIUM,
            "irun": Simulator.XCELIUM,
            "vcs": Simulator.VCS,
            "verilator": Simulator.VERILATOR,
            "dsim": Simulator.DSIM
        }

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=BuildInfo,
                system_prompt="You are an expert in EDA build systems.",
                cwd=str(self.repo_root)
            )

            build_system = build_sys_map.get(result.build_system, BuildSystem.CUSTOM)
            ai_simulators = [sim_map[s] for s in result.simulators if s in sim_map]

            # Merge with regex-detected simulators
            regex_simulators = [sim_map[s] for s in detected_sims if s in sim_map]
            all_simulators = list(set(ai_simulators + regex_simulators))

            return {
                "build_system": build_system,
                "simulators": all_simulators
            }

        except Exception as e:
            tqdm.write(f"[AI Analyzer] Warning: AI build detection failed, using regex fallback")
            # Fallback to regex-only detection
            regex_simulators = [sim_map[s] for s in detected_sims if s in sim_map]
            return {"build_system": BuildSystem.MAKEFILE, "simulators": regex_simulators}