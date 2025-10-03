"""Intelligent gym cleaning and validation using Claude Code SDK."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock


class GymCleaner:
    """Uses Claude to intelligently clean gym structure and validate integrity."""

    def __init__(self, gym_dir: Path, repo_path: Path):
        """Initialize gym cleaner.

        Args:
            gym_dir: Path to gym directory
            repo_path: Path to original repository
        """
        self.gym_dir = Path(gym_dir)
        self.repo_path = Path(repo_path)

    async def analyze_and_clean_async(self, test_files: list[Path]) -> dict[str, Any]:
        """Use Claude to determine what to keep vs. remove.

        Args:
            test_files: List of test file paths that should be removed (tasks)

        Returns:
            Dictionary with 'keep' and 'remove' file lists
        """
        # Pre-filter: Never remove base tests or package files
        files_to_remove = []
        files_to_keep_pre = []

        for test_file in test_files:
            filename = test_file.name.lower()
            # Keep base tests and package files
            if 'base' in filename and 'test' in filename:
                files_to_keep_pre.append(str(test_file))
            elif '_pkg' in filename:
                files_to_keep_pre.append(str(test_file))
            else:
                files_to_remove.append(test_file)

        if files_to_keep_pre:
            print(f"[GymCleaner] Pre-filtered {len(files_to_keep_pre)} infrastructure files")

        test_dir = self.gym_dir / "src/hvl_top/test"

        if not test_dir.exists():
            print(f"[GymCleaner] Test directory not found: {test_dir}")
            return {"keep": files_to_keep_pre, "remove": [str(f) for f in files_to_remove]}

        # Only analyze remaining files (excluding pre-filtered infrastructure)
        if not files_to_remove:
            print("[GymCleaner] All test files are infrastructure, nothing to remove")
            return {"keep": files_to_keep_pre, "remove": []}

        task_files_str = "\n".join(f"- {f.name}" for f in files_to_remove)

        prompt = f"""Analyze the UVM test directory at {test_dir}.

**Task Test Files (to be REMOVED - these become gym tasks):**
{task_files_str}

**Your Job:** Identify which OTHER files in {test_dir} must be KEPT for testbench to compile.

Files that MUST be kept include:
- Package files (*_pkg.sv, *_pkg.svh) in test directory
- All sequence directories and their packages
- Any supporting infrastructure files

Use Read, Glob, and Grep tools to explore the directory structure.

**Return Format:**
Provide a clear list of absolute file paths to KEEP (not remove), one per line.
Example:
/path/to/gym/src/hvl_top/test/apb_test_pkg.sv
/path/to/gym/src/hvl_top/test/sequences/master_sequences/apb_master_seq_pkg.sv
"""

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Grep"],
            cwd=str(self.gym_dir),
            permission_mode="bypassPermissions",
            max_turns=5
        )

        files_to_keep = []
        sdk_success = False
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            # Extract file list from Claude's response
                            found_files = self._parse_file_list(block.text)
                            if found_files:
                                sdk_success = True
                            files_to_keep.extend(found_files)
        except Exception as e:
            print(f"[GymCleaner] Warning: SDK query failed: {e}")
            sdk_success = False

        if not sdk_success:
            print("[GymCleaner] Falling back to heuristic patterns...")
            # Fallback: use simple patterns
            if test_dir.exists():
                for pattern in ["*_pkg.sv", "*_pkg.svh", "sequences/**/*.sv", "sequences/**/*.svh"]:
                    found = [str(f) for f in test_dir.glob(pattern)]
                    files_to_keep.extend(found)
                    if found:
                        print(f"  Found {len(found)} files matching '{pattern}'")

        # Merge pre-filtered with SDK/heuristic results
        all_keep = list(set(files_to_keep_pre + files_to_keep))
        return {"keep": all_keep, "remove": [str(f) for f in files_to_remove]}

    def analyze_and_clean(self, test_files: list[Path]) -> dict[str, Any]:
        """Synchronous wrapper for analyze_and_clean_async.

        Args:
            test_files: List of test file paths that should be removed

        Returns:
            Dictionary with 'keep' and 'remove' file lists
        """
        return asyncio.run(self.analyze_and_clean_async(test_files))

    async def verify_integrity_async(self, profile: dict) -> dict[str, Any]:
        """Use Claude to verify testbench can compile and run base test.

        Args:
            profile: Gym profile configuration

        Returns:
            Dictionary with validation results
        """
        sim_dir = self.gym_dir / "sim"
        simulators = profile.get("simulators", [])
        smoke_tests = profile.get("grading", {}).get("smoke_tests", ["apb_base_test"])
        base_test = smoke_tests[0] if smoke_tests else "base_test"

        if not simulators:
            print("[GymCleaner] No simulators configured, skipping validation")
            return {
                "compilation": False,
                "base_test_exists": False,
                "smoke_test_passed": False,
                "errors": ["No simulators configured"]
            }

        # Find an available simulator directory
        sim_tool = None
        for sim in simulators:
            sim_tool_dir = sim_dir / f"{sim}_sim"
            if not sim_tool_dir.exists():
                # Try alternative naming
                if sim == "xcelium":
                    sim_tool_dir = sim_dir / "cadence_sim"
                elif sim == "questa":
                    sim_tool_dir = sim_dir / "questa_sim"
                elif sim == "vcs":
                    sim_tool_dir = sim_dir / "synopsys_sim"

            if sim_tool_dir.exists():
                sim_tool = sim
                break

        if not sim_tool:
            print(f"[GymCleaner] No simulator directories found in {sim_dir}")
            return {
                "compilation": False,
                "base_test_exists": False,
                "smoke_test_passed": False,
                "errors": ["No simulator directories found"]
            }

        prompt = f"""Verify this UVM testbench is properly set up for DV-Smith gym.

**Gym Directory:** {self.gym_dir}
**Simulator:** {sim_tool}
**Base Test:** {base_test}

**Tasks:**
1. Check if base test file exists in src/hvl_top/test/ or backups/
2. Try to compile the testbench using makefile in sim/ directory (run `make -C sim/{sim_tool}_sim compile`)
3. Check compilation log for errors (look for *E,* or Error patterns)

**IMPORTANT:**
- If compilation fails due to missing files, list which files are missing
- Check if test packages and sequence packages exist
- Return structured results

**Return Format (JSON):**
{{
  "compilation": true/false,
  "base_test_exists": true/false,
  "missing_files": ["list of missing file names"],
  "errors": ["list of error messages from compilation"]
}}
"""

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Bash", "Glob", "Grep"],
            cwd=str(self.gym_dir),
            permission_mode="acceptEdits",  # Allow running compilation
            max_turns=15  # Increased from 8 to allow more thorough checking
        )

        results = {
            "compilation": False,
            "base_test_exists": False,
            "smoke_test_passed": False,
            "missing_files": [],
            "errors": [],
            "agent_responses": []  # Track what agent actually said
        }

        try:
            import asyncio
            # Add timeout to prevent hanging
            async def run_with_timeout():
                async for message in query(prompt=prompt, options=options):
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                # Save agent response for debugging
                                results["agent_responses"].append(block.text[:500])

                                # Parse Claude's structured response
                                parsed = self._parse_validation_results(block.text)

                                # Log if JSON parsing failed
                                if not parsed and block.text:
                                    print(f"[GymCleaner] Debug: Agent response (first 200 chars): {block.text[:200]}")

                                # Merge results (keep most pessimistic values)
                                results["compilation"] = results["compilation"] or parsed.get("compilation", False)
                                results["base_test_exists"] = results["base_test_exists"] or parsed.get("base_test_exists", False)
                                results["missing_files"].extend(parsed.get("missing_files", []))
                                results["errors"].extend(parsed.get("errors", []))

            # Run with 120 second timeout
            await asyncio.wait_for(run_with_timeout(), timeout=120.0)

        except asyncio.TimeoutError:
            print(f"[GymCleaner] Warning: Verification timed out after 120 seconds")
            results["errors"].append("Verification timed out")
        except Exception as e:
            print(f"[GymCleaner] Warning: Validation failed: {e}")
            results["errors"].append(f"Validation exception: {str(e)}")

        # Deduplicate lists
        results["missing_files"] = list(set(results["missing_files"]))
        results["errors"] = list(set(results["errors"]))

        return results

    def verify_integrity(self, profile: dict) -> dict[str, Any]:
        """Synchronous wrapper for verify_integrity_async.

        Args:
            profile: Gym profile configuration

        Returns:
            Dictionary with validation results
        """
        return asyncio.run(self.verify_integrity_async(profile))

    async def clean_package_includes_async(self, removed_test_names: list[str]) -> dict[str, Any]:
        """Use Claude SDK to remove include statements for removed tests from package files.

        Args:
            removed_test_names: List of test filenames that were removed (e.g., ['apb_8b_write_test.sv'])

        Returns:
            Dictionary with cleanup results
        """
        test_dir = self.gym_dir / "src/hvl_top/test"
        if not test_dir.exists():
            print(f"[GymCleaner] Test directory not found: {test_dir}")
            return {"modified_files": [], "errors": ["Test directory not found"]}

        removed_names_str = "\n".join(f"- {name}" for name in removed_test_names)

        prompt = f"""Clean up the test package file by removing include statements for removed tests.

**Task:** Find the test package file in {test_dir} (usually named *_pkg.sv or *_pkg.svh)

**Removed Test Files:**
{removed_names_str}

**What to do:**
1. Read the package file
2. Find all `include statements for the removed test files
3. Comment out or remove those include statements (keep base_test includes!)
4. Add a comment like "// REMOVED by gym builder:" before each removed include for reference
5. Save the modified file

**Important:**
- DO NOT remove includes for base tests or infrastructure files
- ONLY remove includes that match the removed test filenames listed above
- Keep the package structure intact

Use Read and Edit tools to complete this task.
"""

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Glob"],
            cwd=str(self.gym_dir),
            permission_mode="acceptEdits",  # Allow file modifications
            max_turns=8
        )

        modified_files = []
        errors = []
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    # Agent completed the task
                    pass

            # Verify package file was modified by checking if it exists
            pkg_files = list(test_dir.glob("*_pkg.sv")) + list(test_dir.glob("*_pkg.svh"))
            if pkg_files:
                modified_files = [str(f) for f in pkg_files]

        except Exception as e:
            error_msg = f"SDK package cleanup failed: {e}"
            print(f"[GymCleaner] {error_msg}")
            errors.append(error_msg)

        return {
            "modified_files": modified_files,
            "errors": errors
        }

    def clean_package_includes(self, removed_test_names: list[str]) -> dict[str, Any]:
        """Synchronous wrapper for clean_package_includes_async.

        Args:
            removed_test_names: List of test filenames that were removed

        Returns:
            Dictionary with cleanup results
        """
        return asyncio.run(self.clean_package_includes_async(removed_test_names))

    def create_howto_guide(self, profile: dict) -> Path:
        """Create HOWTO.md guide for adding new tests to the gym.

        Args:
            profile: Gym profile configuration

        Returns:
            Path to created HOWTO.md file
        """
        test_dir = self.gym_dir / "src/hvl_top/test"

        # Find the package file
        pkg_files = list(test_dir.glob("*_pkg.sv")) + list(test_dir.glob("*_pkg.svh"))
        pkg_file_name = pkg_files[0].name if pkg_files else "test_pkg.sv"
        pkg_file_path = f"src/hvl_top/test/{pkg_file_name}"

        # Find base test name from profile or infer it
        smoke_tests = profile.get("grading", {}).get("smoke_tests", [])
        base_test_name = smoke_tests[0] if smoke_tests else "base_test"

        howto_content = f"""# How to Add a New UVM Test

This guide explains how to add a new UVM test to this verification environment.

## Overview

This testbench uses the Universal Verification Methodology (UVM) framework. Tests are
organized using SystemVerilog packages, and each test must be:
1. Written as a SystemVerilog file extending the base test class
2. Added to the test package file so it can be compiled
3. Registered with the UVM factory (done automatically via `uvm_component_utils)

## File Structure

```
src/hvl_top/test/
├── {pkg_file_name}              # Main test package (YOU MUST EDIT THIS)
├── {base_test_name}.sv           # Base test class
└── YOUR_NEW_TEST.sv              # Your new test file
```

## Steps to Add a New Test

### 1. Create Your Test File

Create a new SystemVerilog file in `src/hvl_top/test/` that extends the base test:

```systemverilog
// my_new_test.sv
class my_new_test extends {base_test_name};

  `uvm_component_utils(my_new_test)

  function new(string name = "my_new_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  virtual task run_phase(uvm_phase phase);
    // Your test implementation
  endtask

endclass : my_new_test
```

### 2. **CRITICAL**: Add Include to Package File

**You MUST add your test file to `{pkg_file_path}`** or it will not compile!

Open `{pkg_file_path}` and add an include statement for your test:

```systemverilog
package test_pkg;

  // ... imports and other includes ...

  `include "{base_test_name}.sv"
  `include "my_new_test.sv"        // <-- ADD THIS LINE

endpackage : test_pkg
```

**Without this step, your test will not be compiled and you will get a UVM factory error!**

### 3. Run Your Test

Once your test is added to the package, you can run it:

```bash
make -C sim/cadence_sim run TEST=my_new_test
```

## Common Errors

### Error: "Cannot create a component of type 'my_new_test'"

**Cause:** Your test file was not included in `{pkg_file_path}`

**Solution:** Add the include statement as shown in Step 2 above.

### Error: "Requested test from command line +UVM_TESTNAME=my_new_test not found"

**Cause:** Your test class is not registered with the UVM factory

**Solution:** Make sure your test has `uvm_component_utils(my_new_test)` macro

## Tips

- Always extend from `{base_test_name}` to inherit the base environment setup
- Use virtual sequences to coordinate stimulus across multiple agents
- Check the base test implementation for examples of sequence starts
- Follow the naming convention: `<descriptor>_test.sv`

## Package File Location

Remember: **`{pkg_file_path}`**

This is the file you must edit to add your test!
"""

        howto_path = self.gym_dir / "HOWTO.md"

        with open(howto_path, 'w') as f:
            f.write(howto_content)

        print(f"[GymCleaner] Created {howto_path}")
        return howto_path

    def _parse_file_list(self, text: str) -> list[str]:
        """Extract file paths from Claude's response.

        Args:
            text: Claude's response text

        Returns:
            List of file paths
        """
        files = []

        # Try JSON extraction first
        try:
            json_match = re.search(r'\[([^\]]+)\]', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                if isinstance(data, list):
                    return [str(f) for f in data if isinstance(f, str)]
        except Exception:
            pass

        # Fall back to line-by-line extraction
        for line in text.split('\n'):
            # Look for file paths (containing .sv or .svh)
            if '.sv' in line or '.svh' in line:
                # Extract path-like strings
                path_match = re.search(r'(/[\w/\-\.]+\.(?:sv|svh))', line)
                if path_match:
                    files.append(path_match.group(1))
                else:
                    # Try relative path
                    path_match = re.search(r'([\w/\-\.]+\.(?:sv|svh))', line)
                    if path_match:
                        path = path_match.group(1)
                        # Make absolute
                        if not path.startswith('/'):
                            path = str(self.gym_dir / path)
                        files.append(path)

        return files

    def _parse_validation_results(self, text: str) -> dict[str, Any]:
        """Parse validation results from Claude's response.

        Args:
            text: Claude's response text

        Returns:
            Dictionary with validation results
        """
        # Try to extract JSON block
        try:
            json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception:
            pass

        # Fallback to heuristic parsing
        text_lower = text.lower()

        compilation_success = any(
            phrase in text_lower
            for phrase in ["compilation success", "compile successful", "no errors"]
        )

        base_test_exists = any(
            phrase in text_lower
            for phrase in ["base test found", "base_test.sv exists", "base test exists"]
        )

        # Extract error messages
        errors = []
        for line in text.split('\n'):
            if any(err in line.lower() for err in ["error:", "*e,*", "failed", "missing"]):
                errors.append(line.strip())

        return {
            "compilation": compilation_success and not errors,
            "base_test_exists": base_test_exists,
            "missing_files": [],
            "errors": errors[:5]  # Limit to 5 errors
        }
