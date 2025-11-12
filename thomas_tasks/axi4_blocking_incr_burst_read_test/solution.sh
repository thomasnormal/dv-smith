#!/bin/bash
# Solution script - recreates files deleted by clean_repo.sh

set -euo pipefail

cd /axi4_avip

# Create the test file
cat > src/hvl_top/test/axi4_blocking_incr_burst_read_test.sv << 'EOF'
`ifndef AXI4_BLOCKING_INCR_BURST_READ_TEST_INCLUDED_
`define AXI4_BLOCKING_INCR_BURST_READ_TEST_INCLUDED_

//--------------------------------------------------------------------------------------------
// Class: axi4_incr_burst_read_test
// Extends the base test and starts the virtual sequenceof write
//--------------------------------------------------------------------------------------------
class axi4_blocking_incr_burst_read_test extends axi4_base_test;
  `uvm_component_utils(axi4_blocking_incr_burst_read_test)

  //Variable : axi4_virtual_write_seq_h
  //Instantiation of axi4_virtual_write_seq
  axi4_virtual_bk_incr_burst_read_seq axi4_virtual_bk_incr_burst_read_seq_h;

  //-------------------------------------------------------
  // Externally defined Tasks and Functions
  //-------------------------------------------------------
  extern function new(string name = "axi4_blocking_incr_burst_read_test", uvm_component parent = null);
  extern function void setup_axi4_env_cfg();
  extern virtual task run_phase(uvm_phase phase);

endclass : axi4_blocking_incr_burst_read_test

//--------------------------------------------------------------------------------------------
// Construct: new
//
// Parameters:
//  name - axi4_incr_burst_read_test
//  parent - parent under which this component is created
//--------------------------------------------------------------------------------------------
function axi4_blocking_incr_burst_read_test::new(string name = "axi4_blocking_incr_burst_read_test",
                                 uvm_component parent = null);
  super.new(name, parent);
endfunction : new


function void axi4_blocking_incr_burst_read_test::setup_axi4_env_cfg();
  super.setup_axi4_env_cfg();
  axi4_env_cfg_h.write_read_mode_h = ONLY_READ_DATA;
endfunction:setup_axi4_env_cfg
//--------------------------------------------------------------------------------------------
// Task: run_phase
// Creates the axi4_virtual_write_read_seq sequence and starts the write virtual sequences
//
// Parameters:
//  phase - uvm phase
//--------------------------------------------------------------------------------------------
task axi4_blocking_incr_burst_read_test::run_phase(uvm_phase phase);

  axi4_virtual_bk_incr_burst_read_seq_h=axi4_virtual_bk_incr_burst_read_seq::type_id::create("axi4_virtual_bk_incr_burst_read_seq_h");
  `uvm_info(get_type_name(),$sformatf("axi4_blocking_incr_burst_read_test"),UVM_LOW);
  phase.raise_objection(this);
  axi4_virtual_bk_incr_burst_read_seq_h.start(axi4_env_h.axi4_virtual_seqr_h);
  phase.drop_objection(this);

endtask : run_phase

`endif
EOF

# Create the virtual sequence
cat > src/hvl_top/test/virtual_sequences/axi4_virtual_bk_incr_burst_read_seq.sv << 'EOF'
`ifndef AXI4_VIRTUAL_BK_INCR_BURST_READ_SEQ_INCLUDED_
`define AXI4_VIRTUAL_BK_INCR_BURST_READ_SEQ_INCLUDED_

//--------------------------------------------------------------------------------------------
// Class: axi4_virtual_bk_incr_burst_read_seq
// Creates and starts the master and slave sequences
//--------------------------------------------------------------------------------------------
class axi4_virtual_bk_incr_burst_read_seq extends axi4_virtual_base_seq;
  `uvm_object_utils(axi4_virtual_bk_incr_burst_read_seq)

  //Variable: axi4_master_bk_read_incr_burst_seq_h
  //Instantiation of axi4_master_bk_read_incr_burst_seq handle
  axi4_master_bk_read_incr_burst_seq axi4_master_bk_read_incr_burst_seq_h;

  //Variable: axi4_slave_bk_read_incr_burst_seq_h
  //Instantiation of axi4_slave_bk_read_incr_burst_seq handle
  axi4_slave_bk_read_incr_burst_seq axi4_slave_bk_read_incr_burst_seq_h;

  //-------------------------------------------------------
  // Externally defined Tasks and Functions
  //-------------------------------------------------------
  extern function new(string name = "axi4_virtual_bk_incr_burst_read_seq");
  extern task body();
endclass : axi4_virtual_bk_incr_burst_read_seq

//--------------------------------------------------------------------------------------------
// Construct: new
// Initialises new memory for the object
//
// Parameters:
//  name - axi4_virtual_bk_incr_burst_read_seq
//--------------------------------------------------------------------------------------------
function axi4_virtual_bk_incr_burst_read_seq::new(string name = "axi4_virtual_bk_incr_burst_read_seq");
  super.new(name);
endfunction : new

//--------------------------------------------------------------------------------------------
// Task - body
// Creates and starts the data of master and slave sequences
//--------------------------------------------------------------------------------------------
task axi4_virtual_bk_incr_burst_read_seq::body();
  axi4_master_bk_read_incr_burst_seq_h = axi4_master_bk_read_incr_burst_seq::type_id::create("axi4_master_bk_read_incr_burst_seq_h");

  axi4_slave_bk_read_incr_burst_seq_h = axi4_slave_bk_read_incr_burst_seq::type_id::create("axi4_slave_bk_read_incr_burst_seq_h");

  `uvm_info(get_type_name(), $sformatf("DEBUG_MSHA :: Inside axi4_virtual_bk_read_incr_burst_seq"), UVM_NONE);

  fork
    begin : T2_SL_RD
      forever begin
        axi4_slave_bk_read_incr_burst_seq_h.start(p_sequencer.axi4_slave_read_seqr_h);
        //  axi4_slave_nincr_burst_read_seq_h.start(p_sequencer.axi4_slave_read_seqr_h);
      end
    end
  join_none


  fork
    begin: T2_READ
      repeat(3) begin
      axi4_master_bk_read_incr_burst_seq_h.start(p_sequencer.axi4_master_read_seqr_h);
      // axi4_master_nread_incr_burst_seq_h.start(p_sequencer.axi4_master_read_seqr_h);
      end
    end
  join
 endtask : body

`endif
EOF

# Create the master sequence
cat > src/hvl_top/test/sequences/master_sequences/axi4_master_bk_read_incr_burst_seq.sv << 'EOF'
`ifndef AXI4_MASTER_BK_READ_INCR_BURST_SEQ_INCLUDED_
`define AXI4_MASTER_BK_READ_INCR_BURST_SEQ_INCLUDED_

//--------------------------------------------------------------------------------------------
// Class: axi4_master_bk_read_incr_burst_seq
// Extends the axi4_master_bk_base_seq and randomises the req item
//--------------------------------------------------------------------------------------------
class axi4_master_bk_read_incr_burst_seq extends axi4_master_bk_base_seq;
  `uvm_object_utils(axi4_master_bk_read_incr_burst_seq)

  //-------------------------------------------------------
  // Externally defined Tasks and Functions
  //-------------------------------------------------------
  extern function new(string name = "axi4_master_bk_read_incr_burst_seq");
  extern task body();
endclass : axi4_master_bk_read_incr_burst_seq

//--------------------------------------------------------------------------------------------
// Construct: new
// Initializes new memory for the object
//
// Parameters:
//  name - axi4_master_bk_read_incr_burst_seq
//--------------------------------------------------------------------------------------------
function axi4_master_bk_read_incr_burst_seq::new(string name = "axi4_master_bk_read_incr_burst_seq");
  super.new(name);
endfunction : new

//--------------------------------------------------------------------------------------------
// Task: body
// Creates the req of type master_bk transaction and randomises the req
//--------------------------------------------------------------------------------------------
task axi4_master_bk_read_incr_burst_seq::body();
  super.body();
  req.transfer_type=BLOCKING_READ;

  start_item(req);
  if(!req.randomize() with {req.arsize == READ_4_BYTES;
                            req.tx_type == READ;
                            req.arburst == READ_INCR;
                            req.transfer_type == BLOCKING_READ;}) begin

    `uvm_fatal("axi4","Rand failed");
  end
  req.print();
  finish_item(req);

endtask : body

`endif
EOF

# Create the slave sequence
cat > src/hvl_top/test/sequences/slave_sequences/axi4_slave_bk_read_incr_burst_seq.sv << 'EOF'
`ifndef AXI4_SLAVE_BK_READ_INCR_BURST_SEQ_INCLUDED_
`define AXI4_SLAVE_BK_READ_INCR_BURST_SEQ_INCLUDED_

//--------------------------------------------------------------------------------------------
// Class: axi4_slave_bk_read_incr_burst_seq
// Extends the axi4_slave_bk_base_seq and randomises the req item
//--------------------------------------------------------------------------------------------
class axi4_slave_bk_read_incr_burst_seq extends axi4_slave_bk_base_seq;
  `uvm_object_utils(axi4_slave_bk_read_incr_burst_seq)

  //-------------------------------------------------------
  // Externally defined Tasks and Functions
  //-------------------------------------------------------
  extern function new(string name = "axi4_slave_bk_read_incr_burst_seq");
  extern task body();
endclass : axi4_slave_bk_read_incr_burst_seq

//--------------------------------------------------------------------------------------------
// Construct: new
// Initializes new memory for the object
//
// Parameters:
//  name - axi4_slave_bk_read_incr_burst_seq
//--------------------------------------------------------------------------------------------
function axi4_slave_bk_read_incr_burst_seq::new(string name = "axi4_slave_bk_read_incr_burst_seq");
  super.new(name);
endfunction : new

//--------------------------------------------------------------------------------------------
// Task: body
// Creates the req of type slave_bk transaction and randomises the req
//--------------------------------------------------------------------------------------------
task axi4_slave_bk_read_incr_burst_seq::body();
  super.body();
  req.transfer_type=BLOCKING_READ;

  start_item(req);
  if(!req.randomize())begin
    `uvm_fatal("axi4","Rand failed");
  end

  req.print();
  finish_item(req);

endtask : body

`endif
EOF

echo "Solution files created successfully"
