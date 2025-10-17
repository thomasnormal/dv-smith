`ifndef COVERAGE_EVAL_TEST_INCLUDED_
`define COVERAGE_EVAL_TEST_INCLUDED_

`include "uvm_macros.svh"
import uvm_pkg::*;
import axi4_globals_pkg::*;
import axi4_master_pkg::*;
import axi4_slave_pkg::*;
import axi4_env_pkg::*;
import axi4_master_seq_pkg::*;
import axi4_slave_seq_pkg::*;
import axi4_virtual_seq_pkg::*;

class coverage_eval_test extends axi4_base_test;
  `uvm_component_utils(coverage_eval_test)

  function new(string name = "coverage_eval_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  virtual task run_phase(uvm_phase phase);
    phase.raise_objection(this);
    `uvm_info(get_type_name(), "Starting coverage_eval_test", UVM_MEDIUM)

    // Exercise a representative set of sequences to hit burst types, sizes, and lengths
    axi4_virtual_bk_wrap_burst_write_read_seq bk_wrap;
    axi4_virtual_nbk_wrap_burst_write_read_seq nbk_wrap;
    axi4_virtual_bk_incr_burst_write_read_seq bk_incr;
    axi4_virtual_nbk_incr_burst_write_read_seq nbk_incr;
    axi4_virtual_bk_fixed_burst_write_read_seq bk_fixed;
    axi4_virtual_nbk_fixed_burst_write_read_seq nbk_fixed;

    bk_wrap = axi4_virtual_bk_wrap_burst_write_read_seq::type_id::create("bk_wrap");
    nbk_wrap = axi4_virtual_nbk_wrap_burst_write_read_seq::type_id::create("nbk_wrap");
    bk_incr = axi4_virtual_bk_incr_burst_write_read_seq::type_id::create("bk_incr");
    nbk_incr = axi4_virtual_nbk_incr_burst_write_read_seq::type_id::create("nbk_incr");
    bk_fixed = axi4_virtual_bk_fixed_burst_write_read_seq::type_id::create("bk_fixed");
    nbk_fixed = axi4_virtual_nbk_fixed_burst_write_read_seq::type_id::create("nbk_fixed");

    // Small delays between sequences to flush phases
    bk_fixed.start(null);
    #10ns;
    nbk_fixed.start(null);
    #10ns;
    bk_incr.start(null);
    #10ns;
    nbk_incr.start(null);
    #10ns;
    bk_wrap.start(null);
    #10ns;
    nbk_wrap.start(null);

    // Allow scoreboard/coverage to settle
    #100ns;
    phase.drop_objection(this);
  endtask
endclass

`endif
