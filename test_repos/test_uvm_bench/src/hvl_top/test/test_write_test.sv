`ifndef TEST_WRITE_TEST_SV
`define TEST_WRITE_TEST_SV

class test_write_test extends test_base_test;
    `uvm_component_utils(test_write_test)

    test_write_seq write_seq;

    function new(string name = "test_write_test", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual task run_phase(uvm_phase phase);
        phase.raise_objection(this);
        write_seq = test_write_seq::type_id::create("write_seq");
        write_seq.start(env.agent.sequencer);
        phase.drop_objection(this);
    endtask
endclass

`endif
