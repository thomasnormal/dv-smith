Title: Add WLAST Last-Beat Assertion (Static Check)

Intent
- Add an assertion property `AXI_WLAST_LAST_BEAT_CHECK` that verifies `wlast` is asserted only on the final beat of a write burst (beat index == awlen).
- This task focuses on authoring the property in `master_assertions.sv` (static verification).

Procedure
- In `src/hdl_top/master_assertions.sv`, add a property named `AXI_WLAST_LAST_BEAT_CHECK` that informally encodes:
  - When write data channel is active (e.g., while WVALID until WREADY), `wlast` must be 1 only on the last beat dictated by `awlen` and 0 otherwise.
  - You may implement a counter within the property or use temporal sequences to relate the number of W handshakes to `awlen`.
- Bind or instantiate the property in the existing interface context alongside other checks.

Expected Results
- Static evaluation confirms the property exists and includes key temporal structure.
- Future extension (not part of this task): dynamic tests that trip the assertion on a buggy BFM.

Evaluation
- Script: `gym/eval/check_assertion_static.py --property_name AXI_WLAST_LAST_BEAT_CHECK --file src/hdl_top/master_assertions.sv --must_contain wlast --must_contain awlen`.

