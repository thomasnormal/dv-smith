#!/bin/bash
# Remove production tests that overlap with exam tasks
# This prevents students from copy-pasting solutions

set -e

# Ensure that TB_HOME is set
if [ -z "$TB_HOME" ]; then
    echo "Error: TB_HOME environment variable is not set."
    exit 1
fi

TEST_DIR="$TB_HOME/src/hvl_top/test"
PKG_FILE="$TEST_DIR/axi4_test_pkg.sv"

echo "Removing overlapping production tests and example solutions..."

# Remove production test files
rm -f "$TEST_DIR/axi4_blocking_32b_write_read_test.sv"
rm -f "$TEST_DIR/axi4_non_blocking_32b_write_read_test.sv"

# Remove example solution files (created by example_solution.sh)
rm -f "$TEST_DIR/student_example_32b_write_read_test.sv"
rm -f "$TEST_DIR/virtual_sequences/student_example_virtual_seq.sv"

# Remove from package file
sed -i '/axi4_blocking_32b_write_read_test\.sv/d' "$PKG_FILE"
sed -i '/axi4_non_blocking_32b_write_read_test\.sv/d' "$PKG_FILE"
sed -i '/student_example_32b_write_read_test\.sv/d' "$PKG_FILE"

echo "✓ Removed: axi4_blocking_32b_write_read_test.sv"
echo "✓ Removed: axi4_non_blocking_32b_write_read_test.sv"
echo "✓ Removed: student_example_32b_write_read_test.sv"
echo "✓ Removed: student_example_virtual_seq.sv"
echo "✓ Updated: axi4_test_pkg.sv"

# Copy AGENTS.md to repo root
cp /resources/AGENTS.md "$TB_HOME/AGENTS.md"
echo "✓ Copied: AGENTS.md"
