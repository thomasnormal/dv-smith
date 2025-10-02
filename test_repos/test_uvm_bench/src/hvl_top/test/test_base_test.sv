`ifndef TEST_BASE_TEST_SV
`define TEST_BASE_TEST_SV

class test_base_test extends uvm_test;
    `uvm_component_utils(test_base_test)

    test_env env;

    function new(string name = "test_base_test", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        env = test_env::type_id::create("env", this);
    endfunction

    virtual task run_phase(uvm_phase phase);
        phase.raise_objection(this);
        `uvm_info(get_type_name(), "Base test running", UVM_LOW)
        #100ns;
        phase.drop_objection(this);
    endtask
endclass

`endif
