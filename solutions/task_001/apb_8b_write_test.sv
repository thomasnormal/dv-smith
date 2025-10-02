`ifndef APB_8B_WRITE_TEST_INCLUDED_
`define APB_8B_WRITE_TEST_INCLUDED_

//--------------------------------------------------------------------------------------------
// Class: apb_8b_write_test
// Extends the base test and starts the virtual sequence of 8 bit
//--------------------------------------------------------------------------------------------
class apb_8b_write_test extends apb_base_test;
  `uvm_component_utils(apb_8b_write_test)
  
  // Variable: apb_virtual_8b_seq_h
  // Instantiation of apb_virtual_8b_write_seq
  apb_virtual_8b_write_seq apb_virtual_8b_seq_h;

  //-------------------------------------------------------
  // Externally defined Tasks and Functions
  //-------------------------------------------------------
  extern function new(string name = "apb_8b_write_test", uvm_component parent = null);
  extern virtual task build_phase(uvm_phase phase);
  extern virtual task run_phase(uvm_phase phase);

endclass : apb_8b_write_test

//--------------------------------------------------------------------------------------------
// Construct: new
//
// Parameters:
//  name - apb_8b_write_test
//  parent - parent under which this component is created
//--------------------------------------------------------------------------------------------
function apb_8b_write_test::new(string name = "apb_8b_write_test", uvm_component parent = null);
  super.new(name, parent);
endfunction : new

//--------------------------------------------------------------------------------------------
// Task: build_phase
//  Creates the apb_virtual_8b_write_seq and configure it
//--------------------------------------------------------------------------------------------
task apb_8b_write_test::build_phase(uvm_phase phase);
  super.build_phase(phase);
  apb_virtual_8b_seq_h = apb_virtual_8b_write_seq::type_id::create("apb_virtual_8b_seq_h", this);
endtask : build_phase

//--------------------------------------------------------------------------------------------
// Task: run_phase
//  Starts the virtual sequence for the 8-bit write test
//--------------------------------------------------------------------------------------------
task apb_8b_write_test::run_phase(uvm_phase phase);
  `uvm_info(get_type_name(), "Starting 8-bit APB write test...", UVM_MEDIUM)
  phase.raise_objection(this);

  if (!apb_virtual_8b_seq_h.randomize()) begin
    `uvm_error(get_type_name(), "Failed to randomize virtual sequence")
  end

  apb_virtual_8b_seq_h.start(null);
  `uvm_info(get_type_name(), "8-bit APB write test completed.", UVM_MEDIUM)
  
  phase.drop_objection(this);
endtask : run_phase

`endif // APB_8B_WRITE_TEST_INCLUDED_