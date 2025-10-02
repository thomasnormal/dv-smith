`ifndef TEST_READ_SEQ_SV
`define TEST_READ_SEQ_SV

class test_read_seq extends uvm_sequence;
    `uvm_object_utils(test_read_seq)

    function new(string name = "test_read_seq");
        super.new(name);
    endfunction

    virtual task body();
        `uvm_info(get_type_name(), "Executing read sequence", UVM_LOW)
        #50ns;
    endtask
endclass

`endif
