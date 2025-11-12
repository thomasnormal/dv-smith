#!/bin/bash
# Clean repository script - removes files that would give away the solution

set -euo pipefail

cd /axi4_avip

# Remove the test file that contains the solution
rm -f src/hvl_top/test/axi4_blocking_incr_burst_read_test.sv

# Remove the virtual sequence that implements the test logic
rm -f src/hvl_top/test/virtual_sequences/axi4_virtual_bk_incr_burst_read_seq.sv

# Remove any master sequences specific to this test that reveal implementation details
rm -f src/hvl_top/test/sequences/master_sequences/axi4_master_bk_read_incr_burst_seq.sv

# Remove slave sequences specific to this test
rm -f src/hvl_top/test/sequences/slave_sequences/axi4_slave_bk_read_incr_burst_seq.sv

echo "Repository cleaned - solution files removed"
