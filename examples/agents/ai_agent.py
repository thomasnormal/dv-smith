#!/usr/bin/env python3
"""
AI-Powered Agent for DV-Smith

This agent uses OpenAI to generate UVM test solutions based on task specifications.

Usage:
    python examples/agents/ai_agent.py <task_file.md> <output_dir>
"""

import os
import re
import sys
from pathlib import Path

from openai import OpenAI


class AIAgent:
    """An AI-powered agent that generates UVM test code using OpenAI."""

    def __init__(self, task_file: Path) -> None:
        """Initialize agent with task specification.

        Args:
            task_file: Path to task markdown file
        """
        self.task_file = task_file
        self.task_content = task_file.read_text()
        self.task_spec = self._parse_task()

        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")

        self.client = OpenAI(api_key=api_key)

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
            hints = [line.strip("- ").strip()
                    for line in hint_text.split("\n")
                    if line.strip().startswith("-")]

        return {
            "id": task_id_match.group(1) if task_id_match else "unknown",
            "name": task_name_match.group(1).strip() if task_name_match else "Unknown",
            "bench": bench_match.group(1) if bench_match else "unknown",
            "goal": goal_match.group(1).strip() if goal_match else "",
            "description": desc_match.group(1).strip() if desc_match else "",
            "hints": hints,
            "notes": notes_match.group(1).strip() if notes_match else ""
        }

    def generate_solution(self, output_dir: Path) -> Path:
        """Generate a solution using AI.

        Args:
            output_dir: Directory to write solution files

        Returns:
            Path to generated test file
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        print("[AI Agent] Generating solution using OpenAI...")

        # Load reference test if available
        reference_code = ""
        if self.task_spec["notes"]:
            # Try to extract reference file path
            ref_match = re.search(r"Original test:\s*`([^`]+)`", self.task_spec["notes"])
            if ref_match:
                ref_path = Path(ref_match.group(1))
                if ref_path.exists():
                    try:
                        reference_code = ref_path.read_text()[:2000]  # First 2000 chars
                        print(f"[AI Agent] Using reference from: {ref_path.name}")
                    except:
                        pass

        # Generate test code using AI
        test_code = self._generate_with_ai(reference_code)

        # Determine test file name
        class_name = self._extract_class_name(test_code)
        test_file = output_dir / f"{class_name}.sv"
        test_file.write_text(test_code)

        print(f"[AI Agent] Generated test: {test_file}")
        print(f"[AI Agent] Test class: {class_name}")

        return test_file

    def _generate_with_ai(self, reference_code: str = "") -> str:
        """Use OpenAI to generate test code."""

        prompt = f"""You are an expert UVM verification engineer. Generate a complete SystemVerilog UVM test class.

Task: {self.task_spec['name']}
ID: {self.task_spec['id']}

Goal:
{self.task_spec['goal']}

Description:
{self.task_spec['description']}

Hints:
{chr(10).join('- ' + h for h in self.task_spec['hints'])}

"""

        if reference_code:
            prompt += f"""
Reference code (for structure/style):
```systemverilog
{reference_code[:1500]}
```

"""

        prompt += """
Generate a complete SystemVerilog UVM test class that:
1. Extends the appropriate base test class (from hints or use base_test)
2. Implements proper UVM phases (build_phase, run_phase)
3. Creates and configures sequences based on the hints
4. Includes proper UVM macros and utilities
5. Has meaningful logging and error messages
6. Follows UVM best practices

IMPORTANT:
- Include proper include guards (`ifndef, `define, `endif)
- Use correct UVM factory registration
- Configure sequences appropriately for the task
- Return ONLY the SystemVerilog code, no explanations
- Use proper indentation and formatting
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert UVM verification engineer. Generate clean, production-quality SystemVerilog code."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            code = response.choices[0].message.content.strip()

            # Extract code from markdown if present
            if "```systemverilog" in code:
                code = code.split("```systemverilog")[1].split("```")[0].strip()
            elif "```verilog" in code:
                code = code.split("```verilog")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()

            return code

        except Exception as e:
            print(f"[AI Agent] Error generating code: {e}")
            raise

    def _extract_class_name(self, code: str) -> str:
        """Extract class name from generated code."""
        match = re.search(r"class\s+(\w+)\s+extends", code)
        if match:
            return match.group(1)
        return f"{self.task_spec['id']}_test"

    def create_patch(self, output_dir: Path, solution_file: Path) -> Path:
        """Create a git patch file for the solution.

        Args:
            output_dir: Output directory
            solution_file: Path to generated solution file

        Returns:
            Path to patch file
        """
        patch_file = output_dir / "solution.patch"

        # Create a proper git-style patch
        patch_content = f"""diff --git a/tests/{solution_file.name} b/tests/{solution_file.name}
new file mode 100644
index 0000000..{self._git_hash(solution_file.read_text())}
--- /dev/null
+++ b/tests/{solution_file.name}
@@ -0,0 +1,{len(solution_file.read_text().splitlines())} @@
"""

        # Add the content with + prefix
        for line in solution_file.read_text().splitlines():
            patch_content += f"+{line}\n"

        patch_file.write_text(patch_content)
        print(f"[AI Agent] Created patch: {patch_file}")

        return patch_file

    def _git_hash(self, content: str) -> str:
        """Generate a fake git hash for the patch."""
        import hashlib
        return hashlib.sha1(content.encode()).hexdigest()[:7]


def main() -> None:
    """Main entry point for the AI agent."""
    if len(sys.argv) < 3:
        print("Usage: python ai_agent.py <task_file.md> <output_dir>")
        print("\nExample:")
        print("  python ai_agent.py dvsmith_workspace/gyms/apb/tasks/task_001.md solutions/")
        sys.exit(1)

    task_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not task_file.exists():
        print(f"Error: Task file not found: {task_file}")
        sys.exit(1)

    print("=" * 60)
    print("AI Agent for DV-Smith")
    print("=" * 60)
    print(f"Task file: {task_file}")
    print(f"Output directory: {output_dir}")
    print()

    try:
        # Create agent and generate solution
        agent = AIAgent(task_file)

        print("Task Information:")
        print(f"  ID: {agent.task_spec['id']}")
        print(f"  Name: {agent.task_spec['name']}")
        print(f"  Bench: {agent.task_spec['bench']}")
        print(f"  Goal: {agent.task_spec['goal'][:80]}...")
        print(f"  Hints: {len(agent.task_spec['hints'])}")
        print()

        # Generate solution
        solution_file = agent.generate_solution(output_dir)
        patch_file = agent.create_patch(output_dir, solution_file)

        print()
        print("=" * 60)
        print("Solution Generated Successfully!")
        print("=" * 60)
        print(f"Test file: {solution_file}")
        print(f"Patch file: {patch_file}")
        print()
        print("Next steps:")
        print(f"  dvsmith eval --task {task_file} --patch {patch_file}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
