#!/bin/bash
set -e

if [ -z "$TB_HOME" ]; then
    echo "Error: TB_HOME environment variable is not set."
    exit 1
fi

TEST_DIR="$TB_HOME/src/hvl_top/test"
VIRTUAL_SEQ_DIR="$TEST_DIR/virtual_sequences"
MASTER_SEQ_DIR="$TEST_DIR/sequences/master_sequences"

echo "Creating solution files for student_example_incr_burst_write_read_test..."

# Create master write sequence
cat > "$MASTER_SEQ_DIR/student_example_incr_burst_write_seq.sv" << 'EOF'
class student_example_incr_burst_write_seq extends axi4_master_bk_base_seq;

  `uvm_object_utils(student_example_incr_burst_write_seq)

  extern function new(string name = "student_example_incr_burst_write_seq");
  extern task body();
endclass : student_example_incr_burst_write_seq

function student_example_incr_burst_write_seq::new(string name = "student_example_incr_burst_write_seq");
  super.new(name);
endfunction : new

task student_example_incr_burst_write_seq::body();
  super.body();

  start_item(req);
  if(!req.randomize() with {req.awsize == WRITE_2_BYTES;
                              req.tx_type == WRITE;
                              req.transfer_type == BLOCKING_WRITE;
                              req.awburst == WRITE_INCR;}) begin
    `uvm_fatal("axi4","Rand failed");
  end
  finish_item(req);

endtask : body
EOF

# Create master read sequence
cat > "$MASTER_SEQ_DIR/student_example_incr_burst_read_seq.sv" << 'EOF'
class student_example_incr_burst_read_seq extends axi4_master_bk_base_seq;

  `uvm_object_utils(student_example_incr_burst_read_seq)

  extern function new(string name = "student_example_incr_burst_read_seq");
  extern task body();
endclass : student_example_incr_burst_read_seq

function student_example_incr_burst_read_seq::new(string name = "student_example_incr_burst_read_seq");
  super.new(name);
endfunction : new

task student_example_incr_burst_read_seq::body();
  super.body();
  req.transfer_type=BLOCKING_READ;

  start_item(req);
  if(!req.randomize() with {req.arsize == READ_4_BYTES;
                            req.tx_type == READ;
                            req.arburst == READ_INCR;
                            req.transfer_type == BLOCKING_READ;}) begin
    `uvm_fatal("axi4","Rand failed");
  end
  finish_item(req);

endtask : body
EOF

# Create virtual sequence
cat > "$VIRTUAL_SEQ_DIR/student_example_incr_burst_virtual_seq.sv" << 'EOF'
class student_example_incr_burst_virtual_seq extends axi4_virtual_base_seq;

  `uvm_object_utils(student_example_incr_burst_virtual_seq)

  student_example_incr_burst_write_seq axi4_master_write_seq;
  student_example_incr_burst_read_seq axi4_master_read_seq;

  axi4_slave_bk_write_incr_burst_seq axi4_slave_wr_seq;
  axi4_slave_bk_read_incr_burst_seq axi4_slave_rd_seq;

  extern function new(string name = "student_example_incr_burst_virtual_seq");
  extern task body();
endclass : student_example_incr_burst_virtual_seq

function student_example_incr_burst_virtual_seq::new(string name = "student_example_incr_burst_virtual_seq");
  super.new(name);
endfunction : new

task student_example_incr_burst_virtual_seq::body();
  axi4_master_write_seq = student_example_incr_burst_write_seq::type_id::create("axi4_master_write_seq");
  axi4_master_read_seq = student_example_incr_burst_read_seq::type_id::create("axi4_master_read_seq");
  axi4_slave_wr_seq = axi4_slave_bk_write_incr_burst_seq::type_id::create("axi4_slave_wr_seq");
  axi4_slave_rd_seq = axi4_slave_bk_read_incr_burst_seq::type_id::create("axi4_slave_rd_seq");

  fork
    forever begin
      axi4_slave_wr_seq.start(p_sequencer.axi4_slave_write_seqr_h);
    end
  join_none

  fork
    forever begin
      axi4_slave_rd_seq.start(p_sequencer.axi4_slave_read_seqr_h);
    end
  join_none

  repeat(2) begin
    axi4_master_write_seq.start(p_sequencer.axi4_master_write_seqr_h);
  end

  repeat(3) begin
    axi4_master_read_seq.start(p_sequencer.axi4_master_read_seqr_h);
  end

endtask : body
EOF

# Create test
cat > "$TEST_DIR/student_example_incr_burst_write_read_test.sv" << 'EOF'
class student_example_incr_burst_write_read_test extends axi4_base_test;

  `uvm_component_utils(student_example_incr_burst_write_read_test)

  student_example_incr_burst_virtual_seq axi4_virtual_seq_h;

  extern function new(string name = "student_example_incr_burst_write_read_test", uvm_component parent = null);
  extern function void build_phase(uvm_phase phase);
  extern task run_phase(uvm_phase phase);

endclass : student_example_incr_burst_write_read_test

function student_example_incr_burst_write_read_test::new(string name = "student_example_incr_burst_write_read_test", uvm_component parent = null);
  super.new(name, parent);
endfunction : new

function void student_example_incr_burst_write_read_test::build_phase(uvm_phase phase);
  super.build_phase(phase);
endfunction : build_phase

task student_example_incr_burst_write_read_test::run_phase(uvm_phase phase);

  axi4_virtual_seq_h = student_example_incr_burst_virtual_seq::type_id::create("axi4_virtual_seq_h");

  phase.raise_objection(this);

  axi4_virtual_seq_h.start(axi4_env_h.axi4_virtual_seqr_h);
  #100;

  phase.drop_objection(this);

endtask : run_phase
EOF

# Update package files - insert BEFORE endpackage
sed -i '/^endpackage/i \  `include "student_example_incr_burst_write_seq.sv"' "$MASTER_SEQ_DIR/axi4_master_seq_pkg.sv"
sed -i '/^endpackage/i \  `include "student_example_incr_burst_read_seq.sv"' "$MASTER_SEQ_DIR/axi4_master_seq_pkg.sv"
sed -i '/^endpackage/i \  `include "student_example_incr_burst_virtual_seq.sv"' "$VIRTUAL_SEQ_DIR/axi4_virtual_seq_pkg.sv"
sed -i '/^endpackage/i \  `include "student_example_incr_burst_write_read_test.sv"' "$TEST_DIR/axi4_test_pkg.sv"

echo "✓ Solution files created successfully"
