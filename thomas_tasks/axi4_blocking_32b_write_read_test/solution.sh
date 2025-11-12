#!/bin/bash
set -e

# Ensure that TB_HOME is set
if [ -z "$TB_HOME" ]; then
    echo "Error: TB_HOME environment variable is not set."
    exit 1
fi

echo "=================================="
echo "Creating Oracle Solution"
echo "=================================="
echo

# Define paths
TEST_DIR="$TB_HOME/src/hvl_top/test"
VSEQ_DIR="$TB_HOME/src/hvl_top/test/virtual_sequences"
PKG_FILE="$TB_HOME/src/hvl_top/test/axi4_test_pkg.sv"

# Use task-specified names (not original repository names)
TEST_NAME="student_example_32b_write_read_test"
VSEQ_NAME="student_example_virtual_seq"

echo "Step 1: Creating virtual sequence (exact copy from repository)..."

# Create Virtual Sequence - Based on repository code with task-specified naming
cat > "${VSEQ_DIR}/${VSEQ_NAME}.sv" <<'VSEQ_EOF'
`ifndef STUDENT_EXAMPLE_VIRTUAL_SEQ_INCLUDED_
`define STUDENT_EXAMPLE_VIRTUAL_SEQ_INCLUDED_

//--------------------------------------------------------------------------------------------
// Class: student_example_virtual_seq
// Creates and starts the master and slave sequences
//--------------------------------------------------------------------------------------------
class student_example_virtual_seq extends axi4_virtual_base_seq;
  `uvm_object_utils(student_example_virtual_seq)

  //Variable: axi4_master_write_32b_transfer_seq_h
  //Instantiation of axi4_master_write_32b_transfer_seq handle
  axi4_master_bk_write_32b_transfer_seq axi4_master_bk_write_32b_transfer_seq_h;

  //Variable: axi4_master_read_32b_transfer_seq_h
  //Instantiation of axi4_master_read_32b_transfer_seq handle
  axi4_master_bk_read_32b_transfer_seq axi4_master_bk_read_32b_transfer_seq_h;

  //Variable: axi4_slave_write_32b_transfer_seq_h
  //Instantiation of axi4_slave_write_32b_transfer_seq handle
  axi4_slave_bk_write_32b_transfer_seq axi4_slave_bk_write_32b_transfer_seq_h;

  //Variable: axi4_slave_read_32b_transfer_seq_h
  //Instantiation of axi4_slave_read_32b_transfer_seq handle
  axi4_slave_bk_read_32b_transfer_seq axi4_slave_bk_read_32b_transfer_seq_h;

  //-------------------------------------------------------
  // Externally defined Tasks and Functions
  //-------------------------------------------------------
  extern function new(string name = "student_example_virtual_seq");
  extern task body();
endclass : student_example_virtual_seq

//--------------------------------------------------------------------------------------------
// Construct: new
// Initialises new memory for the object
//
// Parameters:
//  name - student_example_virtual_seq
//--------------------------------------------------------------------------------------------
function student_example_virtual_seq::new(string name = "student_example_virtual_seq");
  super.new(name);
endfunction : new

//--------------------------------------------------------------------------------------------
// Task - body
// Creates and starts the data of master and slave sequences
//--------------------------------------------------------------------------------------------
task student_example_virtual_seq::body();

  axi4_master_bk_write_32b_transfer_seq_h = axi4_master_bk_write_32b_transfer_seq::type_id::create("axi4_master_bk_write_32b_transfer_seq_h");

  axi4_master_bk_read_32b_transfer_seq_h = axi4_master_bk_read_32b_transfer_seq::type_id::create("axi4_master_bk_read_32b_transfer_seq_h");

  axi4_slave_bk_write_32b_transfer_seq_h = axi4_slave_bk_write_32b_transfer_seq::type_id::create("axi4_slave_bk_write_32b_transfer_seq_h");

  axi4_slave_bk_read_32b_transfer_seq_h = axi4_slave_bk_read_32b_transfer_seq::type_id::create("axi4_slave_bk_read_32b_transfer_seq_h");
  `uvm_info(get_type_name(), $sformatf("DEBUG_MSHA :: Inside student_example_virtual_seq"), UVM_NONE);

  fork
    begin : T1_SL_WR
      forever begin
        axi4_slave_bk_write_32b_transfer_seq_h.start(p_sequencer.axi4_slave_write_seqr_h);
      end
    end
    begin : T2_SL_RD
      forever begin
        axi4_slave_bk_read_32b_transfer_seq_h.start(p_sequencer.axi4_slave_read_seqr_h);
      end
    end
  join_none


  fork
    begin: T1_WRITE
      repeat(2) begin
        axi4_master_bk_write_32b_transfer_seq_h.start(p_sequencer.axi4_master_write_seqr_h);
      end
    end
    begin: T2_READ
      repeat(3) begin
        axi4_master_bk_read_32b_transfer_seq_h.start(p_sequencer.axi4_master_read_seqr_h);
      end
    end
  join
 endtask : body

`endif

VSEQ_EOF

echo "Step 2: Creating test file (exact copy from repository)..."

# Create Test File - Based on repository code with task-specified naming
cat > "${TEST_DIR}/${TEST_NAME}.sv" <<'TEST_EOF'
`ifndef STUDENT_EXAMPLE_32B_WRITE_READ_TEST_INCLUDED_
`define STUDENT_EXAMPLE_32B_WRITE_READ_TEST_INCLUDED_

//--------------------------------------------------------------------------------------------
// Class: student_example_32b_write_read_test
// Extends the base test and starts the virtual sequence of 32bit write and read sequences
//--------------------------------------------------------------------------------------------
class student_example_32b_write_read_test extends axi4_base_test;
  `uvm_component_utils(student_example_32b_write_read_test)

  //Variable : student_example_virtual_seq_h
  //Instatiation of student_example_virtual_seq
  student_example_virtual_seq student_example_virtual_seq_h;

  //-------------------------------------------------------
  // Externally defined Tasks and Functions
  //-------------------------------------------------------
  extern function new(string name = "student_example_32b_write_read_test", uvm_component parent = null);
  extern virtual task run_phase(uvm_phase phase);

endclass : student_example_32b_write_read_test

//--------------------------------------------------------------------------------------------
// Construct: new
//
// Parameters:
//  name - student_example_32b_write_read_test
//  parent - parent under which this component is created
//--------------------------------------------------------------------------------------------
function student_example_32b_write_read_test::new(string name = "student_example_32b_write_read_test",
                                 uvm_component parent = null);
  super.new(name, parent);
endfunction : new

//--------------------------------------------------------------------------------------------
// Task: run_phase
// Creates the student_example_virtual_seq sequence and starts the write and read virtual sequences
//
// Parameters:
//  phase - uvm phase
//--------------------------------------------------------------------------------------------
task student_example_32b_write_read_test::run_phase(uvm_phase phase);

  student_example_virtual_seq_h=student_example_virtual_seq::type_id::create("student_example_virtual_seq_h");
  `uvm_info(get_type_name(),$sformatf("student_example_32b_write_read_test"),UVM_LOW);
  phase.raise_objection(this);
  student_example_virtual_seq_h.start(axi4_env_h.axi4_virtual_seqr_h);
  phase.drop_objection(this);

endtask : run_phase

`endif

TEST_EOF

echo "Step 3: Updating virtual sequence package..."

# Update virtual sequence package
VSEQ_PKG_FILE="$TB_HOME/src/hvl_top/test/virtual_sequences/axi4_virtual_seq_pkg.sv"

if grep -q "${VSEQ_NAME}" "$VSEQ_PKG_FILE"; then
    echo "  ⚠ Virtual sequence include already exists in package file, skipping..."
else
    ENDPKG_LINE=$(grep -n "^endpackage" "$VSEQ_PKG_FILE" | cut -d: -f1)
    if [ -z "$ENDPKG_LINE" ]; then
        echo "  ✗ ERROR: Could not find endpackage in $VSEQ_PKG_FILE"
        exit 1
    fi
    sed -i "${ENDPKG_LINE}i\  \`include \"${VSEQ_NAME}.sv\"" "$VSEQ_PKG_FILE"
    echo "  ✓ Updated: ${VSEQ_PKG_FILE}"
fi

echo "Step 4: Updating test package..."

if grep -q "${TEST_NAME}" "$PKG_FILE"; then
    echo "  ⚠ Test include already exists in package file, skipping..."
else
    LAST_TEST_LINE=$(grep -n "^[[:space:]]*\`include.*test\.sv" "$PKG_FILE" | tail -1 | cut -d: -f1)
    if [ -z "$LAST_TEST_LINE" ]; then
        echo "  ✗ ERROR: Could not find test includes in $PKG_FILE"
        exit 1
    fi
    sed -i "${LAST_TEST_LINE}a\`include \"${TEST_NAME}.sv\"" "$PKG_FILE"
    echo "  ✓ Updated: ${PKG_FILE}"
fi

echo
echo "=================================="
echo "Solution Created Successfully!"
echo "=================================="
echo
