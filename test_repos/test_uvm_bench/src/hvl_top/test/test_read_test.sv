`ifndef TEST_READ_TEST_SV
`define TEST_READ_TEST_SV

class test_read_test extends test_base_test;
    `uvm_component_utils(test_read_test)

    test_read_seq read_seq;

    function new(string name = "test_read_test", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    virtual task run_phase(uvm_phase phase);
        phase.raise_objection(this);
        read_seq = test_read_seq::type_id::create("read_seq");
        read_seq.start(env.agent.sequencer);
        phase.drop_objection(this);
    endtask
endclass

`endif
