# Task Type: Coverage

Coverage tasks evaluate a learner’s ability to extend SystemVerilog/UVM covergroups and to close targeted coverage holes. Because coverage requires real stimulus, these tasks should integrate with Cadence Xcelium (`xrun`) to generate baseline and post-change reports.

## Overall Structure

- **Target scope** – Identify the covergroup file (for example `src/hvl_top/master/apb_master_coverage.sv`) and constrain edits to the specified covergroup(s).
- **Baseline measurement** – Provide a script to run the existing testbench with `xrun` before any modifications. Capture the initial coverage database so the validator knows which bins remain unhit.
- **Instruction deliverables** – Explain which coverpoints/crosses must be added or adjusted, list the bins that are currently uncovered, and set quantitative goals (for example “close bins `PREADY.wait` and `PWRITE_X_PSLVERR.error`”).
- **Testing harness** – After the learner’s modifications, re-run `xrun`, parse the new coverage reports, and assert that the specified bins are now covered or that the overall percentages have improved beyond a threshold.
- **Reference solution** – Supply minimal modifications that close the named bins without overfitting or altering unrelated coverpoints.

## Simulator Workflow

1. **Baseline run** – `run-tests.sh` should:
   - Compile the design (`xrun -c …`) and run the reference test (`xrun -R …`) prior to any student changes, storing the coverage database (e.g., under `baseline_cov/`).
   - Parse `cov_work/functional.txt` and/or `cov_work/code.txt` to record initial metrics and uncovered bins.
2. **Post-change run** – After the learner’s edits, re-run the same `xrun` flow, writing the updated coverage output to `post_cov/`.
3. **Comparison** – Use a Python script (invoked via pytest or the standard library) to compare baseline vs. post-change results and fail if:
   - The targeted bins remain uncovered.
   - Overall coverage percentages didn’t increase when the task requires an improvement.
4. **Licensing** – Ensure `xrun` picks up the license by exporting `DOCKER_CDS_LIC_FILE` (for example `5280@10.4.120.82`) in the container environment before invoking the simulator.

## Authoring Instructions

- **Context** – Describe the testbench scenario (e.g., APB master environment) and why certain coverage holes exist.
- **Explicit goals** – List each coverpoint/cross/bin that needs attention, along with acceptable values (e.g., “Add bins for `pready` wait states” or “Create cross coverage between `PWRITE` and `PSLVERR` to catch error handling”).
- **Run command** – Tell learners how the automation will execute `xrun` so they can reproduce results locally.
- **Constraints** – Remind learners to preserve existing coverpoints and only add the requested extensions (no removal of existing coverage).

## Testing Guidelines

- **Baseline capture** – If the baseline already meets coverage goals, the test should fail early, alerting the task author to adjust stimulus or requirements.
- **Coverage parsing** – For deterministic validation, read IMC reports (e.g., `functional.txt`) rather than relying on interactive tools. Normalize bin names because IMC can rename them when ranges change.
- **Threshold checks** – Assert that each targeted bin’s hit count meets or exceeds the goal (typically `>= 1` or a specific number). Optionally check overall percentages.
- **Pytest integration** – If using pytest, install it inside the container (via `uv pip install pytest==<version>`) and run `pytest` so the harness captures the summary.

## Reference Solution Expectations

- **Targeted edits** – Add only the coverpoints/crosses/bins requested in the instructions.
- **Maintain structure** – Keep the surrounding covergroup syntax, comments, and existing bins untouched.
- **Deterministic stimulus** – If the solution needs to seed additional stimulus to close bins, make sure it is deterministic so repeated runs produce the same coverage results.
- **Automation ready** – Validate that the provided solution passes the baseline/post-run comparison scripts without manual intervention.

By following these guidelines, coverage tasks will accurately measure coverage closure skills while remaining reproducible inside the Terminal-Bench harness.
