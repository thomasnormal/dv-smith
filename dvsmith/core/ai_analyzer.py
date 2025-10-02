"""AI-powered repository analyzer using Anthropic Claude."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from anthropic import Anthropic

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

        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.client = Anthropic(api_key=api_key)

    def analyze(self) -> RepoAnalysis:
        """Analyze repository using AI.

        Returns:
            Complete RepoAnalysis with all discovered elements
        """
        print("[AI Analyzer] Gathering repository structure...")

        # Step 1: Get directory tree and file list
        file_tree = self._get_file_tree()

        # Step 2: Use AI to identify key directories
        print("[AI Analyzer] Identifying key directories...")
        dir_info = self._identify_directories(file_tree)

        # Step 3: Extract test files and analyze them
        print("[AI Analyzer] Analyzing test files...")
        tests = self._analyze_tests(dir_info.get("tests_dir"))

        # Step 4: Extract sequence files
        print("[AI Analyzer] Analyzing sequences...")
        sequences = self._analyze_sequences(dir_info.get("sequences_dir"))

        # Step 5: Find covergroups
        print("[AI Analyzer] Finding covergroups...")
        covergroups = self._find_covergroups(dir_info)

        # Step 6: Detect build system and simulators
        print("[AI Analyzer] Detecting build system...")
        build_info = self._detect_build_system()

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
        if dir_info.get("tests_dir"):
            analysis.tests_dir = self.repo_root / dir_info["tests_dir"]
        if dir_info.get("sequences_dir"):
            analysis.sequences_dir = self.repo_root / dir_info["sequences_dir"]
        if dir_info.get("env_dir"):
            analysis.env_dir = self.repo_root / dir_info["env_dir"]
        if dir_info.get("agents_dir"):
            analysis.agents_dir = self.repo_root / dir_info["agents_dir"]

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
                timeout=30
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
                timeout=30
            )
            return result.stdout
        except:
            # Last resort: Python walk
            files = []
            for path in self.repo_root.rglob("*.sv"):
                try:
                    rel_path = path.relative_to(self.repo_root)
                    files.append(str(rel_path))
                except:
                    pass
            return "\n".join(files[:100])  # Limit to first 100

    def _identify_directories(self, file_tree: str) -> dict[str, str]:
        """Use AI to identify key directories.

        Args:
            file_tree: Repository structure

        Returns:
            Dictionary with directory paths
        """
        # Get list of directories with test/Test in name AND identify test files by content
        test_dir_candidates = []
        for path in self.repo_root.rglob("*"):
            if path.is_dir() and ("test" in path.name.lower() or "Test" in path.name):
                try:
                    rel = path.relative_to(self.repo_root)
                    sv_files = list(path.glob("*.sv"))

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

                            # Check for UVM test class patterns
                            is_test = (
                                ('class' in content_lower and 'extends' in content_lower) and
                                ('test' in content_lower or 'uvm_test' in content_lower or 'uvm_component' in content_lower)
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
                except:
                    pass

        # Sort by priority (HIGH first) then by count (most tests first)
        test_dir_candidates.sort(key=lambda x: (x["priority"] == "LOW", -x["count"]))

        # If we found exactly one test directory, use it directly (no need for AI to choose)
        if len(test_dir_candidates) == 1:
            print(f"[AI Analyzer] Found single test directory: {test_dir_candidates[0]['path']}")
            return {"tests_dir": test_dir_candidates[0]['path'], "sequences_dir": None, "env_dir": None, "agents_dir": None}

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
- Return null if no suitable directory found

Return ONLY a JSON object.
Example: {{"tests_dir": "src/hvl_top/test", "sequences_dir": "src/hvl_top/sequences", "env_dir": "src/hvl_top/env", "agents_dir": null}}
"""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            temperature=0.1,
            system="You are an expert in SystemVerilog and UVM testbench structure. Return only valid JSON.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        try:
            content = response.content[0].text.strip()
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            dir_info = json.loads(content)

            # Validate that the tests_dir actually exists
            if dir_info.get("tests_dir"):
                test_path = self.repo_root / dir_info["tests_dir"]
                if not test_path.exists():
                    print(f"[AI Analyzer] Warning: AI suggested non-existent path: {dir_info['tests_dir']}")
                    # Use first candidate we actually found
                    if test_dir_candidates:
                        print(f"[AI Analyzer] Using first discovered directory instead: {test_dir_candidates[0]['path']}")
                        dir_info["tests_dir"] = test_dir_candidates[0]['path']
                    else:
                        dir_info["tests_dir"] = None

            return dir_info
        except Exception as e:
            print(f"[AI Analyzer] Warning: Could not parse directory info: {e}")
            # Fallback to first candidate if available
            if test_dir_candidates:
                print(f"[AI Analyzer] Using first discovered directory as fallback: {test_dir_candidates[0]['path']}")
                return {"tests_dir": test_dir_candidates[0]['path'], "sequences_dir": None, "env_dir": None, "agents_dir": None}
            return {}

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
        for test_file in test_file_paths[:100]:
            try:
                content = test_file.read_text()[:5000]  # First 5k chars

                # Quick check if it contains a test class
                if "extends" not in content or "class" not in content:
                    continue

                test_info = self._extract_test_info(test_file, content)
                if test_info:
                    tests.append(test_info)
            except Exception as e:
                print(f"[AI Analyzer] Warning: Could not analyze {test_file}: {e}")

        return tests

    def _find_test_files_with_ai(self, tests_path: Path, dir_tree: str) -> list[Path]:
        """Use AI to identify test files from directory tree.

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

Return a JSON array of ALL relative file paths that might be test classes.
Example: ["SpiBaseTest.sv", "apb_test.sv", "test/my_case.sv"]
"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                temperature=0.1,
                system="You are an expert in UVM directory structures. Return only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            file_paths = json.loads(content)

            # Convert to Path objects
            result = []
            for fpath in file_paths:
                full_path = tests_path / fpath
                if full_path.exists():
                    result.append(full_path)

            # If AI returned empty list or no valid files, use fallback
            if not result:
                print(f"[AI Analyzer] No test files identified by AI, using directory glob")
                return list(tests_path.glob("*.sv"))

            return result

        except Exception as e:
            print(f"[AI Analyzer] Warning: Could not identify test files with AI: {e}")
            # Fallback: find all .sv files in test directory
            return list(tests_path.glob("*.sv"))

    def _extract_test_info(self, file_path: Path, content: str) -> Optional[UVMTest]:
        """Extract test information using AI.

        Args:
            file_path: Path to test file
            content: File content

        Returns:
            UVMTest object or None
        """
        prompt = f"""Analyze this SystemVerilog file and extract UVM TEST class information.

File: {file_path.name}
```systemverilog
{content}
```

IMPORTANT: Only extract if this is a UVM TEST class (extends uvm_test or *_test base class).
Do NOT extract if this is:
- A sequence (extends *_sequence or uvm_sequence)
- A package file (*_pkg.sv)
- A configuration class
- A virtual sequence

Extract:
1. class_name: Name of the TEST class only
2. base_class: What it extends
3. description: Brief description (1 sentence)

Return ONLY valid JSON or null if not a test class.
Example: {{"class_name": "apb_8b_write_test", "base_class": "apb_base_test", "description": "Tests 8-bit write operations"}}
"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                temperature=0.1,
                system="You are an expert in SystemVerilog/UVM. Return only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            if content.lower() == "null" or content.lower() == "none":
                return None

            # Clean up common JSON formatting issues
            # Remove any text after the closing brace/bracket
            if content.startswith('{'):
                # Find the matching closing brace
                brace_count = 0
                for i, char in enumerate(content):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            content = content[:i+1]
                            break
            elif content.startswith('['):
                # Find the matching closing bracket
                bracket_count = 0
                for i, char in enumerate(content):
                    if char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            content = content[:i+1]
                            break

            info = json.loads(content)

            # Handle case where AI returns a list (multiple classes in one file)
            if isinstance(info, list):
                if len(info) > 0:
                    info = info[0]  # Take first test class
                else:
                    return None

            # Validate it's a dict with required fields
            if not isinstance(info, dict) or "class_name" not in info:
                print(f"[AI Analyzer] ERROR: Invalid format from AI for {file_path.name}: {info}")
                return None

            return UVMTest(
                name=info["class_name"],
                file_path=file_path,
                base_class=info.get("base_class", "unknown"),
                description=info.get("description")
            )
        except Exception as e:
            # No fallback - AI must work 100%
            print(f"[AI Analyzer] ERROR: Failed to extract test from {file_path.name}: {e}")
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

                # Simple regex extraction for sequences
                import re
                match = re.search(r"class\s+(\w+)\s+extends\s+(\w+)", content)
                if match and ("seq" in match.group(2).lower() or match.group(2) == "uvm_sequence"):
                    sequences.append(UVMSequence(
                        name=match.group(1),
                        file_path=seq_file,
                        base_class=match.group(2)
                    ))
            except Exception:
                continue

        return sequences

    def _find_covergroups(self, dir_info: dict[str, str]) -> list[str]:
        """Find covergroup definitions using AI.

        Args:
            dir_info: Directory information

        Returns:
            List of covergroup names
        """
        # Search in env and agents directories
        search_dirs = []
        for key in ["env_dir", "agents_dir"]:
            if dir_info.get(key):
                path = self.repo_root / dir_info[key]
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

        prompt = f"""Analyze these build files and identify:
1. Build system type (makefile, cmake, fusesoc, dvsim, or custom)
2. ALL simulators mentioned or supported (questa/modelsim, xcelium/irun/ncsim, vcs, verilator, dsim)

Build files:
```
{build_content[:4000]}
```

Look for:
- Tool commands: vsim, xrun, irun, vcs, verilator, dsim
- Directory names: questa_sim, cadence_sim, synopsys_sim
- Comments mentioning simulators

Return ONLY a JSON object with ALL simulators found.
Example: {{"build_system": "makefile", "simulators": ["questa", "xcelium", "vcs"]}}
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
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                temperature=0.1,
                system="You are an expert in EDA build systems. Return only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # Clean up JSON response - remove extra data after closing brace
            if content.startswith('{'):
                brace_count = 0
                for i, char in enumerate(content):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            content = content[:i+1]
                            break

            info = json.loads(content)

            build_system = build_sys_map.get(info.get("build_system", "custom"), BuildSystem.CUSTOM)
            ai_simulators = [sim_map[s] for s in info.get("simulators", []) if s in sim_map]

            # Merge with regex-detected simulators
            regex_simulators = [sim_map[s] for s in detected_sims if s in sim_map]
            all_simulators = list(set(ai_simulators + regex_simulators))

            return {
                "build_system": build_system,
                "simulators": all_simulators
            }

        except Exception as e:
            print(f"[AI Analyzer] Warning: AI build detection failed, using regex: {e}")
            # Fallback to regex-only detection
            regex_simulators = [sim_map[s] for s in detected_sims if s in sim_map]
            return {"build_system": BuildSystem.MAKEFILE, "simulators": regex_simulators}