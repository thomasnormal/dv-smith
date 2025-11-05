# Task Type: Assertion

Assertion tasks focus on strengthening protocol correctness through SystemVerilog assertions. They should follow a predictable structure so that learners, agents, and validators all have clear expectations.

## Overall Structure

- **Target scope** – Limit edits to a single assertion module (for example `src/hdl_top/master_assertions.sv`). Require the module declaration and port list to remain unchanged.
- **Instruction deliverables** – Spell out every assertion the learner must implement, including signal names, handshake semantics, and the required number of properties.
- **Testing harness** – Provide a deterministic checker that parses the target file and validates the requested properties without running a simulator. Pytest is encouraged, but it must be installed within the container by `run-tests.sh`.
- **Reference solution** – Supply only the minimal assertions needed for the tests to pass; avoid adding unrelated protocol logic or changing interfaces.

## Authoring Instructions

When writing `instructions.md` or `prompt.md`, include the following sections:

1. **Protocol context** – Explain the interface (APB, AXI, etc.) and why each assertion matters.
2. **Explicit requirements** – List every required property (e.g., “AWVALID remains high until AWREADY”). Indicate the exact count so success is unambiguous.
3. **Clock/reset template** – Remind the learner to wrap properties with `@(posedge <clk>) disable iff (!<reset_n>)`.
4. **Structural guardrails** – Tell the learner to keep the module name, parameter list, and port order intact and to replace TODO blocks only.
5. **Labeling/error text** – Encourage meaningful labels and `$error` messages to aid debug if assertions fail at runtime.

## Testing Guidelines

Assertion tasks typically avoid simulator runs; the validator examines the source. Recommended checks:

- **File existence** – Verify the target file is present.
- **Module integrity** – Ensure `module <name>` and `endmodule` remain, and the port list matches exactly.
- **TODO removal** – Fail if TODO comments persist in the target file.
- **Property/assert parity** – Count `property` definitions and `assert property` statements and confirm they match the requested number. Each property should be asserted.
- **Clock/reset template** – Use regex to confirm every property contains the expected clocking and reset disable clause.
- **Signal patterns** – Search for the specific handshake patterns (for example `(awvalid && !awready) |=> awvalid`). Mirror the exact text you asked for in the instructions so false positives are unlikely.
- **Pytest output** – If `parser_name` is `pytest`, install pytest inside `run-tests.sh` (commonly via `uv pip install pytest==<version>`). Invoke `pytest $TEST_DIR/test_outputs.py -rA` so the harness captures the summary.

## Reference Solution Expectations

- **Minimal completeness** – Implement only the requested assertions and nothing else.
- **Template compliance** – All properties must use the required clocking/reset form and include descriptive labels/messages.
- **No structural drift** – Preserve module headers, port ordering, parameters, and comments unrelated to the TODO area.
- **Self-contained** – The solution script should overwrite the target file with the finished implementation or apply a patch; avoid relying on extra tooling.

Following these guidelines keeps assertion tasks predictable and easy to validate while still exercising protocol reasoning skills.
