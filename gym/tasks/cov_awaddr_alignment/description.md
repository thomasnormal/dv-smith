Title: Add AW Address Alignment Coverpoint and Test It

Intent
- Add a new coverpoint `AWADDR_ALIGNMENT_CP` in master coverage that classifies write addresses as `ALIGNED` vs `UNALIGNED` based on `awaddr % (2**awsize)`.
- Add a cross `AWSIZE_CP_X_AWADDR_ALIGNMENT_CP` to correlate size with alignment.
- Create a targeted UVM test `axi4_unaligned_awaddr_test` that hits the `UNALIGNED` bin at least once.

Procedure
- Modify `src/hvl_top/master/axi4_master_coverage.sv`:
  - Define coverpoint `AWADDR_ALIGNMENT_CP` with bins `ALIGNED`, `UNALIGNED` (use derived field or sampled expression).
  - Define cross `AWSIZE_CP_X_AWADDR_ALIGNMENT_CP`.
- Author `src/hvl_top/test/axi4_unaligned_awaddr_test.sv` and any needed sequences to generate unaligned write (and optionally read) transfers.
- Include the test in `src/hvl_top/test/axi4_test_pkg.sv`.

Expected Results
- Log is clean (no `UVM_ERROR`, `UVM_FATAL`, `Error`).
- coverage.txt shows:
  - `Coverpoint : AWADDR_ALIGNMENT_CP` exists.
  - Bin `AWADDR_ALIGNMENT_CP.UNALIGNED` has hits ≥ 1.
  - Cross `AWSIZE_CP_X_AWADDR_ALIGNMENT_CP` appears (optional check).

Evaluation
- Script: `gym/eval/check_coverpoint_task.py axi4_unaligned_awaddr_test --coverpoint AWADDR_ALIGNMENT_CP --bins UNALIGNED --min_hits 1`.

