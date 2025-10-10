"""Intelligent gym cleaning and validation using Claude Code SDK."""

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage
from pydantic import BaseModel, Field

from ..config import get_logger
from .ai_structured import query_with_pydantic_response

logger = get_logger(__name__)


class PackageCleanupResult(BaseModel):
    """Result of package file cleanup."""

    modified_files: list[str] = Field(
        default_factory=list, description="List of package files that were modified"
    )
    removed_includes: list[str] = Field(
        default_factory=list, description="List of include statements that were removed"
    )
    success: bool = Field(description="True if cleanup completed successfully")
    notes: str = Field(default="", description="Any notes or warnings about the cleanup")


class ValidationResult(BaseModel):
    """Result of testbench validation."""

    compilation: bool = Field(description="True if compilation succeeded, False otherwise")
    base_test_exists: bool = Field(description="True if base test file exists")
    missing_files: list[str] = Field(
        default_factory=list,
        description="List of missing file names that caused compilation to fail",
    )
    errors: list[str] = Field(
        default_factory=list, description="List of error messages from compilation"
    )


class FileList(BaseModel):
    """List of files to keep."""

    files_to_keep: list[str] = Field(
        default_factory=list,
        description="List of absolute file paths that must be kept for testbench to compile",
    )


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
            if "base" in filename and "test" in filename:
                files_to_keep_pre.append(str(test_file))
            elif "_pkg" in filename:
                files_to_keep_pre.append(str(test_file))
            else:
                files_to_remove.append(test_file)

        if files_to_keep_pre:
            logger.info(f"Pre-filtered {len(files_to_keep_pre)} infrastructure files")

        test_dir = self.gym_dir / "src/hvl_top/test"

        if not test_dir.exists():
            logger.warning(f"Test directory not found: {test_dir}")
            return {"keep": files_to_keep_pre, "remove": [str(f) for f in files_to_remove]}

        # Only analyze remaining files (excluding pre-filtered infrastructure)
        if not files_to_remove:
            logger.info("All test files are infrastructure, nothing to remove")
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

Explore the directory structure and return the list of absolute file paths to keep.
"""

        files_to_keep = []
        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=FileList,
                system_prompt="You are an expert in UVM testbench structure.",
                cwd=str(self.gym_dir),
            )
            files_to_keep = result.files_to_keep
        except Exception as e:
            logger.warning(f"SDK query failed: {e}")
            logger.info("Falling back to heuristic patterns...")
            # Fallback: use simple patterns
            if test_dir.exists():
                for pattern in ["*_pkg.sv", "*_pkg.svh", "sequences/**/*.sv", "sequences/**/*.svh"]:
                    found = [str(f) for f in test_dir.glob(pattern)]
                    files_to_keep.extend(found)
                    if found:
                        logger.info(f"Found {len(found)} files matching '{pattern}'")

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
            logger.info("No simulators configured, skipping validation")
            return {
                "compilation": False,
                "base_test_exists": False,
                "smoke_test_passed": False,
                "errors": ["No simulators configured"],
            }

        # Find an available simulator directory and check if tools are installed
        sim_tool = None
        sim_tool_dir = None
        for sim in simulators:
            candidate_dir = sim_dir / f"{sim}_sim"
            if not candidate_dir.exists():
                # Try alternative naming
                if sim == "xcelium":
                    candidate_dir = sim_dir / "cadence_sim"
                elif sim == "questa":
                    candidate_dir = sim_dir / "questa_sim"
                elif sim == "vcs":
                    candidate_dir = sim_dir / "synopsys_sim"

            if candidate_dir.exists():
                # Check if simulator tools are actually available
                import subprocess

                tool_check = None
                if sim == "xcelium":
                    tool_check = "xrun"
                elif sim == "questa":
                    tool_check = "vsim"
                elif sim == "vcs":
                    tool_check = "vcs"

                if tool_check:
                    try:
                        result = subprocess.run(
                            ["which", tool_check], capture_output=True, timeout=5
                        )
                        if result.returncode == 0:
                            sim_tool = sim
                            sim_tool_dir = candidate_dir
                            break
                    except:
                        pass

        if not sim_tool:
            logger.warning(f"No available simulator tools found in {sim_dir}")
            return {
                "compilation": False,
                "base_test_exists": False,
                "smoke_test_passed": False,
                "errors": ["No available simulator tools found (check PATH)"],
            }

        logger.info(f"Using {sim_tool} for validation at {sim_tool_dir}")

        prompt = f"""Verify this UVM testbench is properly set up for DV-Smith gym.

**Gym Directory:** {self.gym_dir}
**Simulator:** {sim_tool}
**Base Test:** {base_test}

**Tasks:**
1. Check if base test file exists in src/hvl_top/test/ or backups/
2. Try to compile the testbench using makefile in sim/ directory (run `make -C sim/{sim_tool}_sim compile`)
3. Check compilation log for errors (look for *E,* or Error patterns)

**IMPORTANT:**
- If compilation fails due to missing files, list which files are missing in the missing_files array
- Check if test packages and sequence packages exist
- Set compilation to true only if compilation succeeded with no errors
- Set base_test_exists to true if you find the base test file

Analyze the testbench and return your findings.
"""

        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=ValidationResult,
                system_prompt="You are an expert in UVM testbench validation.",
                cwd=str(self.gym_dir),
            )

            return {
                "compilation": result.compilation,
                "base_test_exists": result.base_test_exists,
                "smoke_test_passed": False,  # Not tested yet
                "missing_files": result.missing_files,
                "errors": result.errors,
            }
        except Exception as e:
            logger.warning(f"Validation failed: {e}")
            return {
                "compilation": False,
                "base_test_exists": False,
                "smoke_test_passed": False,
                "missing_files": [],
                "errors": [f"Validation exception: {str(e)}"],
            }

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
            logger.warning(f"Test directory not found: {test_dir}")
            return {"modified_files": [], "errors": ["Test directory not found"]}

        removed_names_str = "\n".join(f"- {name}" for name in removed_test_names)

        prompt = f"""Remove include statements for deleted test files from the test package file.

**Test directory:** {test_dir}

**Removed Test Files:**
{removed_names_str}

**Your task:**
1. Find the test package file (usually named *_pkg.sv or *_pkg.svh)
2. Remove all `include statements that reference the removed test files listed above
3. DO NOT remove base tests or infrastructure files
4. ONLY remove includes that exactly match the removed test filenames

**Example:**
If removed file is "apb_8b_write_test.sv", remove:
`include "apb_8b_write_test.sv"

Use the edit_file tool to make the changes. Return the list of modified files.
"""

        modified_files = []
        errors = []
        try:
            result = await query_with_pydantic_response(
                prompt=prompt,
                response_model=PackageCleanupResult,
                system_prompt="You are an expert in UVM package file structure and include management.",
                cwd=str(self.gym_dir),
            )

            modified_files = result.modified_files
            if not result.success and result.notes:
                errors.append(result.notes)

        except Exception as e:
            error_msg = f"SDK package cleanup failed: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        return {"modified_files": modified_files, "errors": errors}

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

        with open(howto_path, "w") as f:
            f.write(howto_content)

        logger.info(f"Created {howto_path}")
        return howto_path
