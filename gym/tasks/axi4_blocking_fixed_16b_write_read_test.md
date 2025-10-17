Title: AXI4 Blocking Fixed-Burst 16-bit Write/Read

Intent
- Verify fixed-burst (BURST=FIXED) transfers for both write and read.
- Exercise 16-bit (2-byte) transfer size on both channels.
- Validate data integrity via scoreboard and hit relevant coverage bins.

Procedure
- Start the virtual sequence `axi4_virtual_bk_fixed_16b_write_read_seq`.
  - Master issues a few fixed-burst writes (size=2 bytes), then fixed-burst reads (size=2 bytes).
  - Slave fixed-burst sequences respond accordingly.
- Keep default environment config from `axi4_base_test`.

Expected Results
- No `UVM_ERROR`, `UVM_FATAL`, or simulator `Error` in the test log.
- Scoreboard evidence in the log includes at least one instance of:
  - `SB_awburst_MATCHED` with value `'h0` (FIXED), and `SB_awsize_MATCHED` with value `'h1` (2 bytes).
  - `SB_arburst_MATCHED` with value `'h0` (FIXED), and `SB_arsize_MATCHED` with value `'h1` (2 bytes).
  - `SB_wdata_MATCHED` and `SB_rdata_MATCHED` at least once.
- Coverage:
  - `AWSIZE_CP.AWSIZE_2BYTES` and `ARSIZE_CP.ARSIZE_2BYTES` bins reported with ≥ 1 hit in `coverage.txt`.

Files to Add
- Test: `src/hvl_top/test/axi4_blocking_fixed_16b_write_read_test.sv` (extends `axi4_base_test`).
- Virtual seq: `src/hvl_top/test/virtual_sequences/axi4_virtual_bk_fixed_16b_write_read_seq.sv`.
- Master seq: `src/hvl_top/test/sequences/master_sequences/axi4_master_bk_read_fixed_16b_seq.sv`.

How It’s Evaluated
- Compile: `make -C sim/questasim compile args=+DATA_WIDTH=32`
- Simulate: `make -C sim/questasim simulate test=axi4_blocking_fixed_16b_write_read_test uvm_verbosity=UVM_LOW`
- Autograder: `python3 gym/eval/eval_one.py axi4_blocking_fixed_16b_write_read_test`
  - Fails if any of: log errors present; scoreboard evidence missing; `coverage.txt` missing or required bins absent.

