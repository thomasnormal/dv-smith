Title: Coverage Closure ≥ 40% Within 60s

Intent
- Create an orchestrating UVM test `axi4_closure_test` that drives sequences to raise master+slave average coverage to at least 40%.
- Keep runtime within 60 seconds (wall clock) on a typical Questa setup.

Procedure
- Author `src/hvl_top/test/axi4_closure_test.sv` that starts a virtual sequence blending bursts, sizes, and address patterns.
- You may add or reuse sequences under `src/hvl_top/test/sequences/**` and `src/hvl_top/test/virtual_sequences/**`.
- Register the test in `src/hvl_top/test/axi4_test_pkg.sv`.

Expected Results
- Log contains no `UVM_ERROR`, `UVM_FATAL`, or `Error`.
- Reported coverage in the log shows:
  - `AXI4 Master Agent Coverage = X%`
  - `AXI4 Slave Agent Coverage = Y%`
  - average (X+Y)/2 ≥ 40%.
- Simulation completes within 60 seconds.

Evaluation
- Script: `gym/eval/check_closure.py axi4_closure_test --threshold 40 --timeout_s 60`.

