`ifndef TEST_PKG_SV
`define TEST_PKG_SV

package test_pkg;
    `include "uvm_macros.svh"
    import uvm_pkg::*;

    `include "test_write_seq.sv"
    `include "test_read_seq.sv"
    `include "test_env.sv"
    `include "test_base_test.sv"
    `include "test_write_test.sv"
    `include "test_read_test.sv"
endpackage

`endif
