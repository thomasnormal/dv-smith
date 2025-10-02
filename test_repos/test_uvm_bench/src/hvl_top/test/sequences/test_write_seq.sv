`ifndef TEST_WRITE_SEQ_SV
`define TEST_WRITE_SEQ_SV

class test_write_seq extends uvm_sequence;
    `uvm_object_utils(test_write_seq)

    function new(string name = "test_write_seq");
        super.new(name);
    endfunction

    virtual task body();
        `uvm_info(get_type_name(), "Executing write sequence", UVM_LOW)
        #50ns;
    endtask
endclass

`endif
