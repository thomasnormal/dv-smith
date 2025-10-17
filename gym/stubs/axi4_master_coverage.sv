`ifndef AXI4_MASTER_COVERAGE_INCLUDED_
`define AXI4_MASTER_COVERAGE_INCLUDED_

// AXI4 Master Coverage stub
// Implement the required coverpoints and crosses per task YAML.

class axi4_master_coverage extends uvm_subscriber #(axi4_master_tx);
  `uvm_component_utils(axi4_master_coverage)

  axi4_master_agent_config axi4_master_agent_cfg_h;

  covergroup axi4_master_covergroup with function sample (axi4_master_agent_config cfg, axi4_master_tx packet);
    option.per_instance = 1;

    // TODO: Implement required coverpoints with EXACT names:
    // - AWLEN_CP, AWBURST_CP, AWSIZE_CP
    // - ARLEN_CP, ARBURST_CP, ARSIZE_CP
    // and crosses:
    // - AWLENGTH_CP_X_AWSIZE_X_AWBURST
    // - ARLENGTH_CP_X_ARSIZE_X_ARBURST

  endgroup: axi4_master_covergroup

  extern function new(string name = "axi4_master_coverage", uvm_component parent = null);
  extern virtual function void write(axi4_master_tx t);
  extern virtual function void report_phase(uvm_phase phase);
endclass : axi4_master_coverage

function axi4_master_coverage::new(string name = "axi4_master_coverage", uvm_component parent = null);
  super.new(name, parent);
  axi4_master_covergroup = new();
endfunction : new

function void axi4_master_coverage::write(axi4_master_tx t);
  axi4_master_covergroup.sample(axi4_master_agent_cfg_h, t);
endfunction: write

function void axi4_master_coverage::report_phase(uvm_phase phase);
  `uvm_info(get_type_name(), $sformatf("AXI4 Master Agent Coverage = %0.2f %%", axi4_master_covergroup.get_coverage()), UVM_NONE)
endfunction: report_phase

`endif

