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
VIRTUAL_SEQ_DIR="$TEST_DIR/virtual_sequences"
MASTER_SEQ_DIR="$TEST_DIR/sequences/master_sequences"

echo "Removing overlapping production tests and example solutions..."

# Remove production test files for incr burst tests
rm -f "$TEST_DIR/axi4_blocking_incr_burst_write_read_test.sv"
rm -f "$TEST_DIR/axi4_non_blocking_incr_burst_write_read_test.sv"
rm -f "$TEST_DIR/axi4_blocking_incr_burst_write_test.sv"
rm -f "$TEST_DIR/axi4_blocking_incr_burst_read_test.sv"
rm -f "$TEST_DIR/axi4_non_blocking_incr_burst_write_test.sv"
rm -f "$TEST_DIR/axi4_non_blocking_incr_burst_read_test.sv"

# Remove virtual sequence files that would give away the solution OR reference deleted master sequences
rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_bk_incr_burst_write_read_seq.sv"
rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_nbk_incr_burst_write_read_seq.sv"
rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_bk_incr_burst_write_seq.sv"
rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_bk_incr_burst_read_seq.sv"
rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_nbk_incr_burst_write_seq.sv"
rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_nbk_incr_burst_read_seq.sv"

# Remove production master sequence files that would give away the solution
rm -f "$MASTER_SEQ_DIR/axi4_master_bk_write_incr_burst_seq.sv"
rm -f "$MASTER_SEQ_DIR/axi4_master_bk_read_incr_burst_seq.sv"

# Remove example solution files (created by solution.sh)
rm -f "$TEST_DIR/student_example_incr_burst_write_read_test.sv"
rm -f "$VIRTUAL_SEQ_DIR/student_example_incr_burst_virtual_seq.sv"
rm -f "$MASTER_SEQ_DIR/student_example_incr_burst_write_seq.sv"
rm -f "$MASTER_SEQ_DIR/student_example_incr_burst_read_seq.sv"

# Remove from package file - CRITICAL: Use backtick format
sed -i '/`include "axi4_blocking_incr_burst_write_read_test\.sv"/d' "$PKG_FILE"
sed -i '/`include "axi4_non_blocking_incr_burst_write_read_test\.sv"/d' "$PKG_FILE"
sed -i '/`include "axi4_blocking_incr_burst_write_test\.sv"/d' "$PKG_FILE"
sed -i '/`include "axi4_blocking_incr_burst_read_test\.sv"/d' "$PKG_FILE"
sed -i '/`include "axi4_non_blocking_incr_burst_write_test\.sv"/d' "$PKG_FILE"
sed -i '/`include "axi4_non_blocking_incr_burst_read_test\.sv"/d' "$PKG_FILE"
sed -i '/`include "student_example_incr_burst_write_read_test\.sv"/d' "$PKG_FILE"

# Remove from virtual sequence package
VIRTUAL_PKG="$VIRTUAL_SEQ_DIR/axi4_virtual_seq_pkg.sv"
if [ -f "$VIRTUAL_PKG" ]; then
    sed -i '/`include "axi4_virtual_bk_incr_burst_write_read_seq\.sv"/d' "$VIRTUAL_PKG"
    sed -i '/`include "axi4_virtual_nbk_incr_burst_write_read_seq\.sv"/d' "$VIRTUAL_PKG"
    sed -i '/`include "axi4_virtual_bk_incr_burst_write_seq\.sv"/d' "$VIRTUAL_PKG"
    sed -i '/`include "axi4_virtual_bk_incr_burst_read_seq\.sv"/d' "$VIRTUAL_PKG"
    sed -i '/`include "axi4_virtual_nbk_incr_burst_write_seq\.sv"/d' "$VIRTUAL_PKG"
    sed -i '/`include "axi4_virtual_nbk_incr_burst_read_seq\.sv"/d' "$VIRTUAL_PKG"
    sed -i '/`include "student_example_incr_burst_virtual_seq\.sv"/d' "$VIRTUAL_PKG"
fi

# Remove from master sequence package
MASTER_PKG="$MASTER_SEQ_DIR/axi4_master_seq_pkg.sv"
if [ -f "$MASTER_PKG" ]; then
    sed -i '/`include "axi4_master_bk_write_incr_burst_seq\.sv"/d' "$MASTER_PKG"
    sed -i '/`include "axi4_master_bk_read_incr_burst_seq\.sv"/d' "$MASTER_PKG"
    sed -i '/`include "student_example_incr_burst_write_seq\.sv"/d' "$MASTER_PKG"
    sed -i '/`include "student_example_incr_burst_read_seq\.sv"/d' "$MASTER_PKG"
fi

echo "✓ Removed: axi4_blocking_incr_burst_write_read_test.sv and related files"
echo "✓ Updated: package files"

# Copy AGENTS.md to repo root
cp /resources/AGENTS.md "$TB_HOME/AGENTS.md"
echo "✓ Copied: AGENTS.md"
