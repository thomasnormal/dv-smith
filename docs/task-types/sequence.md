# Task Type: Sequence / Testbench Stimulus

Sequence tasks evaluate a learner’s ability to extend UVM stimulus—either by creating new sequences, modifying virtual sequences, or updating tests that drive transactions through the bench.

## Overall Structure

- **Target scope** – Specify which sequence/test file(s) must be modified (for example `src/hvl_top/test/sequences/master_sequences/apb_burst_seq.sv` or `src/hvl_top/test/apb_random_test.sv`). Limit changes to those files unless additional package updates are explicitly required.
- **Instruction deliverables** – Describe the transaction pattern to implement, including ordering, constraints, and any edge cases (error responses, back-to-back operations, etc.).
- **Testing harness** – Provide a source-level checker that confirms the new sequence exists, inherits from the correct base class, registers with the factory, and calls expected API methods. Optionally complement with runtime checks using `xrun` to ensure the sequence executes without UVM errors.
- **Reference solution** – Implement the minimal stimulus to satisfy the instructions while maintaining coding style and factory registration conventions.

## Authoring Instructions

- **Behavior narrative** – Explain what the sequence/test should do (e.g., “Issue a write burst, then issue a read with wait states, and verify the scoreboard results”).
- **Implementation requirements** – List methods that must be overridden (`body`, `pre_body`), constraints to apply, and any configuration knobs to set (e.g., `cfg.hasCoverage = 1`).
- **Integration steps** – Remind learners to register the sequence with the factory (`luvm_object_utils`) and, if necessary, update testlists or virtual sequences.
- **Simulator expectations** – If the validator will run `xrun`, state the command and any environment setup so the learner can replicate the flow locally.

## Testing Guidelines

- **Static checks** – Confirm the new class is present, extends the required base (e.g., `extends apb_master_base_seq`), and registers with the factory. Ensure method bodies call the expected UVM APIs (`start_item`, `finish_item`, etc.).
- **Configuration validation** – Verify that tests update environment configuration or scoreboard hooks as described in the instructions.
- **Runtime smoke test (optional)** – Use `xrun` to build and run the modified test, checking the simulation log for `UVM_ERROR`, `UVM_FATAL`, or assertion failures. Install required dependencies inside the container and ensure `DOCKER_CDS_LIC_FILE` is set if simulation is enabled.
- **Pytest wrapping** – As with other task types, use pytest (installed via `uv pip install pytest==<version>`) when `parser_name` is `pytest`, so the harness captures the structured output.

## Reference Solution Expectations

- **Minimal stimulus** – Implement only the sequences/tests requested, avoiding extra transactions beyond the requirements.
- **Factory-ready** – Include proper registration macros and ensure the sequence can be created by name.
- **Deterministic behavior** – Seed or constrain randomization to keep simulation results reproducible if runtime validation is used.
- **Clean integration** – Leave existing sequences intact and keep coding style consistent with the repository (indentation, logging macros, etc.).

Adhering to these guidelines keeps sequence tasks focused on stimulus development while remaining compatible with automated validation and, when needed, simulator-based smoke tests.
