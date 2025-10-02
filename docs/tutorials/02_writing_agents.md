# Writing Agents for DV-Smith

This tutorial teaches you how to write agents that can solve UVM verification tasks automatically.

## What is an Agent?

An agent is a program that:
1. Reads a task specification (Markdown file)
2. Generates SystemVerilog/UVM code (tests, sequences, etc.)
3. Creates a patch file with the solution
4. Optionally validates the solution before submission

## Agent Interface

### Input

Agents receive a task specification file (`.md`) that contains:

```markdown
# Task: 8b_write

**ID:** `8b_write`
**Level:** medium
**Bench:** apb_avip

## Goal
Test 8-bit APB write transactions

## Description
Write a UVM test and sequence(s) that exercise 8-bit write operations...

## Hints
- Use apb_write_seq as base
- Configure pdata to 8 bits
- Verify pstrb signal

## Acceptance Criteria
### Functional Coverage
- Minimum: 80.0%
- Target bins: apb_tx_cg.cp_pdata

### Code Coverage
- Statements: ≥70.0%
- Branches: ≥60.0%
```

### Output

Agents must produce:
1. **Solution files**: SystemVerilog test/sequence files
2. **Patch file**: Git diff showing changes

## Claude SDK Agent (Recommended)

The most powerful agent implementation uses the Claude Code SDK to autonomously generate UVM test code. See `examples/agents/claude_sdk_agent.py`:

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

class ClaudeSDKAgent:
    """An agent that uses Claude Code SDK to generate UVM test code."""

    def __init__(self, task_file: Path):
        self.task_file = task_file
        self.task_spec = self._parse_task()

    async def generate_solution(self, output_dir: Path):
        """Generate solution using Claude Code SDK."""
        # Get gym root directory
        gym_root = self.task_file.parent.parent.resolve()

        # Configure SDK options
        options = ClaudeAgentOptions(
            allowed_tools=["Write", "Read", "Edit", "Glob"],
            permission_mode="acceptEdits",
            cwd=str(gym_root),
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": "You are an expert UVM verification engineer."
            }
        )

        # Generate solution
        modified_files = []
        async with ClaudeSDKClient(options=options) as client:
            await client.query(self._build_prompt())

            async for message in client.receive_response():
                # Track file modifications
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        if block.name in ["Write", "Edit"]:
                            file_path = block.input.get("file_path")
                            modified_files.append(file_path)

        return modified_files, gym_root
```

**Key Features:**
- **Autonomous**: Claude reads HOWTO.md, edits package files, and creates tests
- **Multi-file**: Can modify multiple files (test + package)
- **Context-aware**: Understands UVM structure from repository
- **Self-correcting**: Can iterate on solutions

**Usage:**
```bash
python examples/agents/claude_sdk_agent.py \
    gym/tasks/task_008_8b_write.md \
    solutions/task_008
```

## Simple Agent Example

Here's a minimal template-based agent:

```python
#!/usr/bin/env python3
import sys
import re
from pathlib import Path

class SimpleAgent:
    def __init__(self, task_file: Path):
        self.task_spec = self._parse_task(task_file)

    def _parse_task(self, task_file: Path) -> dict:
        """Extract key information from task markdown."""
        content = task_file.read_text()

        # Extract task ID
        task_id = re.search(r'\*\*ID:\*\*\s*`([^`]+)`', content).group(1)

        # Extract goal
        goal = re.search(r'## Goal\n(.+?)(?=\n##)', content, re.DOTALL).group(1).strip()

        # Extract hints
        hints_section = re.search(r'## Hints\n(.+?)(?=\n##)', content, re.DOTALL)
        hints = [line.strip('- ') for line in hints_section.group(1).split('\n')
                if line.strip().startswith('-')]

        return {'id': task_id, 'goal': goal, 'hints': hints}

    def generate_solution(self, output_dir: Path) -> Path:
        """Generate UVM test code."""
        test_code = f'''
class {self.task_spec['id']}_test extends base_test;
    `uvm_component_utils({self.task_spec['id']}_test)

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    virtual task run_phase(uvm_phase phase);
        my_sequence seq;
        phase.raise_objection(this);

        seq = my_sequence::type_id::create("seq");
        // Configure based on hints: {self.task_spec['hints']}
        seq.start(env.agent.sequencer);

        phase.drop_objection(this);
    endtask
endclass
'''

        test_file = output_dir / f"{self.task_spec['id']}_test.sv"
        test_file.write_text(test_code)
        return test_file

if __name__ == "__main__":
    task_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    agent = SimpleAgent(task_file)
    agent.generate_solution(output_dir)
```

## Advanced Agent Techniques

### 1. LLM-Powered Agents

Use Claude to generate sophisticated solutions:

```python
from anthropic import Anthropic

class ClaudeLLMAgent:
    def __init__(self, task_file: Path):
        self.client = Anthropic()  # Reads ANTHROPIC_API_KEY from env
        self.task_spec = self._parse_task(task_file)

    def generate_solution(self, output_dir: Path) -> Path:
        # Create prompt for Claude
        prompt = f"""Generate a SystemVerilog UVM test for:
Goal: {self.task_spec['goal']}
Hints: {', '.join(self.task_spec['hints'])}

Requirements:
- Extend base_test
- Use proper UVM phases
- Create and configure sequences based on hints
- Add appropriate UVM messaging
- Include proper include guards
"""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            system="You are an expert UVM verification engineer with deep knowledge of SystemVerilog and UVM methodology."
        )

        code = response.content[0].text

        # Extract code from markdown if present
        if '```systemverilog' in code:
            code = code.split('```systemverilog')[1].split('```')[0]

        test_file = output_dir / f"{self.task_spec['id']}_test.sv"
        test_file.write_text(code)
        return test_file
```

**Note**: For even better results, use the **Claude SDK Agent** (above) which can autonomously read repository context and make multi-file edits.

### 2. Template-Based Agents

Use templates for consistent code structure:

```python
from jinja2 import Template

UVM_TEST_TEMPLATE = Template('''
class {{ class_name }} extends {{ base_class }};
    `uvm_component_utils({{ class_name }})

    function new(string name = "{{ class_name }}", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual task run_phase(uvm_phase phase);
        {% for seq_name in sequences %}
        {{ seq_name }} {{ seq_name }}_inst;
        {% endfor %}

        phase.raise_objection(this);

        {% for seq_name in sequences %}
        {{ seq_name }}_inst = {{ seq_name }}::type_id::create("{{ seq_name }}_inst");
        {% if config %}
        // Configuration
        {% for key, value in config.items() %}
        {{ seq_name }}_inst.{{ key }} = {{ value }};
        {% endfor %}
        {% endif %}
        {{ seq_name }}_inst.start(env.agent.sequencer);
        {% endfor %}

        phase.drop_objection(this);
    endtask
endclass
''')

class TemplateAgent:
    def generate_solution(self, task_spec: dict, output_dir: Path):
        # Analyze hints to extract sequences and config
        sequences = self._extract_sequences(task_spec['hints'])
        config = self._extract_config(task_spec['hints'])

        code = UVM_TEST_TEMPLATE.render(
            class_name=f"{task_spec['id']}_test",
            base_class="base_test",
            sequences=sequences,
            config=config
        )

        test_file = output_dir / f"{task_spec['id']}_test.sv"
        test_file.write_text(code)
        return test_file
```

### 3. Multi-File Agents

Generate both tests and sequences:

```python
class MultiFileAgent:
    def generate_solution(self, output_dir: Path):
        files = []

        # Generate sequence
        seq_file = self._generate_sequence(output_dir)
        files.append(seq_file)

        # Generate test
        test_file = self._generate_test(output_dir)
        files.append(test_file)

        # Create patch for all files
        patch_file = self._create_patch(files, output_dir)

        return patch_file

    def _generate_sequence(self, output_dir: Path) -> Path:
        seq_code = '''
class custom_seq extends base_sequence;
    `uvm_object_utils(custom_seq)

    rand int num_trans;

    constraint default_c {
        num_trans inside {[10:50]};
    }

    virtual task body();
        repeat(num_trans) begin
            `uvm_do(req)
        end
    endtask
endclass
'''
        seq_file = output_dir / "custom_seq.sv"
        seq_file.write_text(seq_code)
        return seq_file

    def _generate_test(self, output_dir: Path) -> Path:
        test_code = '''
class my_test extends base_test;
    `uvm_component_utils(my_test)

    virtual task run_phase(uvm_phase phase);
        custom_seq seq;
        phase.raise_objection(this);
        seq = custom_seq::type_id::create("seq");
        seq.num_trans = 100;
        seq.start(env.agent.sequencer);
        phase.drop_objection(this);
    endtask
endclass
'''
        test_file = output_dir / "my_test.sv"
        test_file.write_text(test_code)
        return test_file
```

### 4. Iterative Refinement Agents

Agents that validate and refine solutions:

```python
class IterativeAgent:
    def generate_solution(self, task_file: Path, output_dir: Path, max_iterations=3):
        for iteration in range(max_iterations):
            print(f"Iteration {iteration + 1}/{max_iterations}")

            # Generate solution
            solution = self._generate_code(task_file)
            self._write_solution(solution, output_dir)

            # Validate syntax
            if not self._validate_syntax(output_dir):
                print("Syntax errors found, refining...")
                continue

            # Quick simulation check (optional)
            if self._quick_simulate(output_dir):
                print("Solution validated successfully!")
                break

            print("Simulation failed, refining...")

        return self._create_patch(output_dir)

    def _validate_syntax(self, output_dir: Path) -> bool:
        """Check SystemVerilog syntax."""
        # Use verilator or similar for syntax checking
        import subprocess
        result = subprocess.run(
            ['verilator', '--lint-only', str(output_dir / '*.sv')],
            capture_output=True
        )
        return result.returncode == 0
```

## Best Practices

### 1. Parse Task Specifications Carefully

```python
def parse_task(task_file: Path) -> dict:
    """Robust task parsing."""
    content = task_file.read_text()

    spec = {}

    # Required fields
    spec['id'] = re.search(r'\*\*ID:\*\*\s*`([^`]+)`', content).group(1)
    spec['bench'] = re.search(r'\*\*Bench:\*\*\s*(\S+)', content).group(1)

    # Goal and description
    goal_match = re.search(r'## Goal\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
    spec['goal'] = goal_match.group(1).strip() if goal_match else ''

    # Parse hints
    hints_match = re.search(r'## Hints\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
    if hints_match:
        spec['hints'] = [
            line.strip('- ').strip()
            for line in hints_match.group(1).split('\n')
            if line.strip().startswith('-')
        ]
    else:
        spec['hints'] = []

    # Parse acceptance criteria
    func_cov = re.search(r'Minimum:\s*(\d+\.?\d*)%', content)
    spec['min_functional_cov'] = float(func_cov.group(1)) if func_cov else 80.0

    code_cov = re.search(r'Statements:\s*≥(\d+\.?\d*)%', content)
    spec['min_code_cov'] = float(code_cov.group(1)) if code_cov else 70.0

    return spec
```

### 2. Generate Valid SystemVerilog

```python
def generate_valid_sv(class_name: str, sequences: list) -> str:
    """Generate syntactically correct SystemVerilog."""
    code = f"`ifndef {class_name.upper()}_SV\n"
    code += f"`define {class_name.upper()}_SV\n\n"
    code += f"class {class_name} extends base_test;\n"
    code += f"    `uvm_component_utils({class_name})\n\n"
    code += f"    function new(string name = \"{class_name}\", "
    code += "uvm_component parent = null);\n"
    code += "        super.new(name, parent);\n"
    code += "    endfunction\n\n"
    code += "    // ... implementation\n\n"
    code += "endclass\n\n"
    code += f"`endif // {class_name.upper()}_SV\n"
    return code
```

### 3. Create Proper Patch Files

```python
def create_patch(solution_files: list, output_dir: Path) -> Path:
    """Create a git patch file."""
    import subprocess

    # Initialize git repo if needed
    if not (output_dir / '.git').exists():
        subprocess.run(['git', 'init'], cwd=output_dir)
        subprocess.run(['git', 'add', '.'], cwd=output_dir)
        subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=output_dir)

    # Add new files
    for f in solution_files:
        subprocess.run(['git', 'add', str(f)], cwd=output_dir)

    # Create diff
    result = subprocess.run(
        ['git', 'diff', '--cached'],
        cwd=output_dir,
        capture_output=True,
        text=True
    )

    patch_file = output_dir / 'solution.patch'
    patch_file.write_text(result.stdout)

    return patch_file
```

### 4. Handle Edge Cases

```python
def safe_generate(agent, task_file, output_dir):
    """Wrapper with error handling."""
    try:
        return agent.generate_solution(task_file, output_dir)
    except Exception as e:
        print(f"Error generating solution: {e}")

        # Generate minimal fallback solution
        fallback_test = '''
class fallback_test extends base_test;
    `uvm_component_utils(fallback_test)
    virtual task run_phase(uvm_phase phase);
        phase.raise_objection(this);
        #100ns;
        phase.drop_objection(this);
    endtask
endclass
'''
        fallback_file = output_dir / 'fallback_test.sv'
        fallback_file.write_text(fallback_test)
        return fallback_file
```

## Testing Your Agent

### Unit Test

```python
def test_agent():
    # Create mock task
    task_content = '''
# Task: test_simple
**ID:** `test_simple`
## Goal
Simple test goal
## Hints
- Use simple_seq
'''
    task_file = Path('/tmp/task.md')
    task_file.write_text(task_content)

    # Run agent
    output_dir = Path('/tmp/solution')
    output_dir.mkdir(exist_ok=True)

    agent = SimpleAgent(task_file)
    solution = agent.generate_solution(output_dir)

    # Verify
    assert solution.exists()
    assert 'test_simple' in solution.read_text()
    print("Agent test passed!")
```

### Integration Test

```bash
# Test on real gym
python my_agent.py \
    dvsmith_workspace/gyms/apb_avip/tasks/task_001_8b_write.md \
    test_output/

# Evaluate the solution
dvsmith eval \
    --task dvsmith_workspace/gyms/apb_avip/tasks/task_001_8b_write.md \
    --patch test_output/solution.patch \
    --sim xcelium
```

## Example: Complete Agent

See `examples/agents/claude_sdk_agent.py` for a complete working example that:
- Parses task specifications with regex
- Uses Claude Code SDK for autonomous code generation
- Reads HOWTO.md and follows repository conventions
- Modifies multiple files (test + package files)
- Creates git patch files
- Tracks all file modifications
- Provides detailed progress output

**Quick Start:**
```bash
# Make sure ANTHROPIC_API_KEY is set
export ANTHROPIC_API_KEY=your-key-here

# Run the Claude SDK agent
python examples/agents/claude_sdk_agent.py \
    dvsmith_workspace/gyms/apb_avip/tasks/task_008_8b_write.md \
    solutions/task_008

# Output:
#   [Claude SDK Agent] Generating solution using Claude Code...
#   [Claude SDK Agent] Working in gym directory: /path/to/gym
#   [Claude SDK Agent] Claude created: src/hvl_top/test/apb_8b_write_test.sv
#   [Claude SDK Agent] Claude edited: src/hvl_top/test/apb_test_pkg.sv
#   [Claude SDK Agent] Modified 2 file(s)
#   [Claude SDK Agent] Created patch: solutions/task_008/solution.patch
```

## Next Steps

- **[Understanding Evaluation](03_evaluation.md)**: Learn how solutions are scored
- **[Advanced Agent Techniques](04_advanced_agents.md)**: RAG, multi-modal, ensemble methods
- Join our community to share agents and benchmarks