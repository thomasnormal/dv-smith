#!/usr/bin/env python3
"""
Claude SDK Agent for DV-Smith

This agent uses Claude Code SDK to generate UVM test solutions based on task specifications.
It leverages Claude's coding capabilities through the SDK to create sophisticated verification code.

Usage:
    python examples/agents/claude_sdk_agent.py <task_file.md> <output_dir>
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
    )
except ImportError:
    print("Error: claude-agent-sdk not installed")
    print("Install with: pip install claude-agent-sdk")
    sys.exit(1)


class ClaudeSDKAgent:
    """An agent that uses Claude Code SDK to generate UVM test code."""

    def __init__(self, task_file: Path) -> None:
        """Initialize agent with task specification.

        Args:
            task_file: Path to task markdown file
        """
        self.task_file = task_file
        self.task_content = task_file.read_text()
        self.task_spec = self._parse_task()

    def _parse_task(self) -> dict:
        """Parse task specification from markdown."""
        content = self.task_content

        # Extract key information
        task_id_match = re.search(r"\*\*ID:\*\*\s*`([^`]+)`", content)
        task_name_match = re.search(r"# Task:\s*(.+)", content)
        bench_match = re.search(r"\*\*Bench:\*\*\s*(\S+)", content)
        goal_match = re.search(r"## Goal\n(.+?)(?=\n##|\Z)", content, re.DOTALL)
        desc_match = re.search(r"## Description\n(.+?)(?=\n##|\Z)", content, re.DOTALL)
        hints_match = re.search(r"## Hints\n(.+?)(?=\n##|\Z)", content, re.DOTALL)
        notes_match = re.search(r"## Notes\n(.+?)(?=\n##|\Z)", content, re.DOTALL)

        # Extract hints as list
        hints = []
        if hints_match:
            hint_text = hints_match.group(1)
            hints = [
                line.strip("- ").strip()
                for line in hint_text.split("\n")
                if line.strip().startswith("-")
            ]

        # Extract acceptance criteria
        func_cov_match = re.search(r"Minimum:\s*(\d+\.?\d*)%", content)
        code_cov_match = re.search(r"Statements:\s*≥(\d+\.?\d*)%", content)

        return {
            "id": task_id_match.group(1) if task_id_match else "unknown",
            "name": task_name_match.group(1).strip() if task_name_match else "Unknown",
            "bench": bench_match.group(1) if bench_match else "unknown",
            "goal": goal_match.group(1).strip() if goal_match else "",
            "description": desc_match.group(1).strip() if desc_match else "",
            "hints": hints,
            "notes": notes_match.group(1).strip() if notes_match else "",
            "min_functional_cov": float(func_cov_match.group(1))
            if func_cov_match
            else 80.0,
            "min_code_cov": float(code_cov_match.group(1)) if code_cov_match else 70.0,
        }

    async def generate_solution(self, output_dir: Path) -> tuple[list[str], Path]:
        """Generate a solution using Claude Code SDK.

        Args:
            output_dir: Directory to write solution files

        Returns:
            Tuple of (list of modified file paths relative to gym root, gym root path)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        print("[Claude SDK Agent] Generating solution using Claude Code...")

        # Build the prompt for Claude
        prompt = self._build_prompt()

        # Get gym root directory (task files are in gym/tasks/)
        gym_root = self.task_file.parent.parent.resolve()  # Make absolute
        print(f"[Claude SDK Agent] Working in gym directory: {gym_root}")

        # Configure SDK options
        options = ClaudeAgentOptions(
            allowed_tools=["Write", "Read", "Edit", "Glob"],
            permission_mode="acceptEdits",
            cwd=str(gym_root),
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": "You are an expert UVM verification engineer. Generate clean, production-quality SystemVerilog code that follows UVM best practices.",
            },
        )

        # Use ClaudeSDKClient to generate the solution
        modified_files = []  # Track all files Claude modifies
        test_file = None
        test_code = ""

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            # Process responses to extract generated code and track file modifications
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            # Extract code from response if present
                            if "```systemverilog" in block.text:
                                code = block.text.split("```systemverilog")[1].split(
                                    "```"
                                )[0]
                                test_code += code.strip()
                        elif isinstance(block, ToolUseBlock):
                            if block.name == "Write":
                                # Claude wrote a file
                                file_path = block.input.get("file_path", "")
                                if file_path:
                                    file_path_obj = Path(file_path)
                                    if file_path_obj.is_absolute():
                                        # Make relative to gym root
                                        file_path_obj = file_path_obj.relative_to(gym_root)
                                    modified_files.append(str(file_path_obj))
                                    if file_path.endswith(".sv"):
                                        test_file = Path(file_path)
                                    print(
                                        f"[Claude SDK Agent] Claude created: {file_path_obj}"
                                    )
                            elif block.name == "Edit":
                                # Claude edited a file
                                file_path = block.input.get("file_path", "")
                                if file_path:
                                    file_path_obj = Path(file_path)
                                    if file_path_obj.is_absolute():
                                        # Make relative to gym root
                                        file_path_obj = file_path_obj.relative_to(gym_root)
                                    if str(file_path_obj) not in modified_files:
                                        modified_files.append(str(file_path_obj))
                                    print(
                                        f"[Claude SDK Agent] Claude edited: {file_path_obj}"
                                    )

        # Report what files were modified
        if modified_files:
            print(f"[Claude SDK Agent] Modified {len(modified_files)} file(s):")
            for f in modified_files:
                print(f"  - {f}")
            return modified_files, gym_root

        # If Claude didn't modify any files, check for extracted code
        if test_code:
            print(
                "[Claude SDK Agent] Warning: No files modified by Claude, writing extracted code..."
            )
            class_name = self._extract_class_name(test_code)
            test_file = output_dir / f"{class_name}.sv"
            test_file.write_text(test_code)
            print(f"[Claude SDK Agent] Generated test: {test_file}")
            return [str(test_file)], output_dir

        # Fallback: generate a basic test manually
        print(
            "[Claude SDK Agent] Warning: Could not extract code, generating fallback..."
        )
        test_file = output_dir / f"{self.task_spec['id']}_test.sv"
        test_file.write_text(self._generate_fallback_test())
        return [str(test_file)], output_dir

    def _build_prompt(self) -> str:
        """Build a comprehensive prompt for Claude."""
        prompt = f"""Generate a complete SystemVerilog UVM test class for the following verification task:

**Task:** {self.task_spec['name']}
**Task ID:** {self.task_spec['id']}
**Bench:** {self.task_spec['bench']}

**Goal:**
{self.task_spec['goal']}

**Description:**
{self.task_spec['description']}

**Hints:**
{chr(10).join('- ' + h for h in self.task_spec['hints'])}

**CRITICAL - Getting Started Instructions:**
The task specification includes a "Getting Started" section that states:
"IMPORTANT: Before implementing your solution, read the HOWTO.md file in the gym root directory.
It contains critical information about:
- How to add tests to the package file (required for compilation)
- UVM test structure and base classes
- Common errors and how to fix them"

YOU MUST:
1. **FIRST**: Read the HOWTO.md file in the current directory to understand how to add tests to this repository
2. Follow ALL steps described in HOWTO.md, including any package file updates or include statements
3. Ensure your test will be found by the UVM factory and can compile successfully
4. Make ALL necessary file modifications (test file + any package/configuration files mentioned in HOWTO.md)

**Requirements:**
1. Create a complete SystemVerilog UVM test class that extends the appropriate base test
2. Implement proper UVM phases (build_phase, run_phase)
3. Create and configure sequences based on the hints
4. Use UVM factory registration with `uvm_component_utils
5. Include proper include guards (`ifndef, `define, `endif)
6. Add meaningful UVM info messages for debugging
7. Follow UVM best practices and coding standards

**Coverage Goals:**
- Functional Coverage: >{self.task_spec['min_functional_cov']}%
- Code Coverage: >{self.task_spec['min_code_cov']}%

Follow the HOWTO.md instructions carefully to ensure your test compiles and runs correctly.
"""

        if self.task_spec["notes"]:
            prompt += f"\n**Additional Notes:**\n{self.task_spec['notes']}\n"

        return prompt

    def _extract_class_name(self, code: str) -> str:
        """Extract class name from generated code."""
        match = re.search(r"class\s+(\w+)\s+extends", code)
        if match:
            return match.group(1)
        return f"{self.task_spec['id']}_test"

    def _generate_fallback_test(self) -> str:
        """Generate a basic fallback test if Claude fails."""
        class_name = self.task_spec["id"].replace("-", "_") + "_test"

        return f"""`ifndef {class_name.upper()}_SV
`define {class_name.upper()}_SV

// Task: {self.task_spec['id']}
// Goal: {self.task_spec['goal']}
// Generated by Claude SDK Agent (fallback)

class {class_name} extends base_test;

    `uvm_component_utils({class_name})

    function new(string name = "{class_name}", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        `uvm_info(get_type_name(), "Build phase", UVM_LOW)
    endfunction

    virtual task run_phase(uvm_phase phase);
        base_sequence seq;

        phase.raise_objection(this);
        `uvm_info(get_type_name(), "Starting test", UVM_MEDIUM)

        seq = base_sequence::type_id::create("seq");
        seq.start(env.agent.sequencer);

        `uvm_info(get_type_name(), "Test completed", UVM_MEDIUM)
        phase.drop_objection(this);
    endtask

endclass

`endif // {class_name.upper()}_SV
"""

    def create_patch(
        self, output_dir: Path, modified_files: list[str], gym_root: Path
    ) -> Path:
        """Create a git patch file for the solution.

        Args:
            output_dir: Output directory for patch file
            modified_files: List of file paths relative to gym_root
            gym_root: Root directory of the gym

        Returns:
            Path to patch file
        """
        patch_file = output_dir / "solution.patch"
        patch_content = ""

        # Generate patch for each modified file
        for file_path in modified_files:
            full_path = gym_root / file_path
            if not full_path.exists():
                print(f"[Claude SDK Agent] Warning: File not found: {full_path}")
                continue

            content = full_path.read_text()
            lines = content.splitlines()

            # Create patch entry for this file
            patch_content += f"""diff --git a/{file_path} b/{file_path}
new file mode 100644
index 0000000..{self._git_hash(content)}
--- /dev/null
+++ b/{file_path}
@@ -0,0 +1,{len(lines)} @@
"""

            # Add the content with + prefix
            for line in lines:
                patch_content += f"+{line}\n"

            patch_content += "\n"  # Blank line between files

        patch_file.write_text(patch_content)
        print(f"[Claude SDK Agent] Created patch: {patch_file}")
        print(f"[Claude SDK Agent] Patch includes {len(modified_files)} file(s)")

        return patch_file

    def _git_hash(self, content: str) -> str:
        """Generate a fake git hash for the patch."""
        import hashlib

        return hashlib.sha1(content.encode()).hexdigest()[:7]


async def main_async() -> None:
    """Async main entry point for the Claude SDK agent."""
    if len(sys.argv) < 3:
        print("Usage: python claude_sdk_agent.py <task_file.md> <output_dir>")
        print("\nExample:")
        print(
            "  python claude_sdk_agent.py dvsmith_workspace/gyms/apb/tasks/task_001.md solutions/"
        )
        sys.exit(1)

    task_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not task_file.exists():
        print(f"Error: Task file not found: {task_file}")
        sys.exit(1)

    print("=" * 60)
    print("Claude SDK Agent for DV-Smith")
    print("=" * 60)
    print(f"Task file: {task_file}")
    print(f"Output directory: {output_dir}")
    print()

    try:
        # Create agent and generate solution
        agent = ClaudeSDKAgent(task_file)

        print("Task Information:")
        print(f"  ID: {agent.task_spec['id']}")
        print(f"  Name: {agent.task_spec['name']}")
        print(f"  Bench: {agent.task_spec['bench']}")
        print(f"  Goal: {agent.task_spec['goal'][:80]}...")
        print(f"  Min Functional Coverage: {agent.task_spec['min_functional_cov']}%")
        print(f"  Min Code Coverage: {agent.task_spec['min_code_cov']}%")
        print(f"  Hints: {len(agent.task_spec['hints'])}")
        print()

        # Generate solution
        modified_files, gym_root = await agent.generate_solution(output_dir)
        patch_file = agent.create_patch(output_dir, modified_files, gym_root)

        print()
        print("=" * 60)
        print("Solution Generated Successfully!")
        print("=" * 60)
        print(f"Modified files ({len(modified_files)}):")
        for f in modified_files:
            print(f"  - {f}")
        print(f"Patch file: {patch_file}")
        print()
        print("Next steps:")
        print(f"  dvsmith eval --task {task_file} --patch {patch_file}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Main entry point for the Claude SDK agent."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
