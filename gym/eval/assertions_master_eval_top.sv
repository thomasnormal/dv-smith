// Evaluation top for t1_master_assertions
// Instantiates the tb that drives channel signals and binds the master_assertions interface
// Then runs positive and negative subtests to exercise assertions.

`timescale 1ns/1ps

// Import TB that defines tasks for pos/neg cases
`include "tb_master_assertions.sv"

module assertions_master_eval_top;
  // Instantiate TB module containing signals and tasks
  tb_master_assertions tb();

  // Instantiate the assertions interface under test and wire to TB signals
  master_assertions M_A (
    .aclk(tb.aclk),
    .aresetn(tb.aresetn),
    .awid(tb.awid),
    .awaddr(tb.awaddr),
    .awlen(tb.awlen),
    .awsize(tb.awsize),
    .awburst(tb.awburst),
    .awlock(tb.awlock),
    .awcache(tb.awcache),
    .awprot(tb.awprot),
    .awvalid(tb.awvalid),
    .awready(tb.awready),
    .wdata(tb.wdata),
    .wstrb(tb.wstrb),
    .wlast(tb.wlast),
    .wuser(tb.wuser),
    .wvalid(tb.wvalid),
    .wready(tb.wready),
    .bid(tb.bid),
    .bresp(tb.bresp),
    .buser(tb.buser),
    .bvalid(tb.bvalid),
    .bready(tb.bready),
    .arid(tb.arid),
    .araddr(tb.araddr),
    .arlen(tb.arlen),
    .arsize(tb.arsize),
    .arburst(tb.arburst),
    .arlock(tb.arlock),
    .arcache(tb.arcache),
    .arprot(tb.arprot),
    .arqos(tb.arqos),
    .arregion(tb.arregion),
    .aruser(tb.aruser),
    .arvalid(tb.arvalid),
    .arready(tb.arready),
    .rid(tb.rid),
    .rdata(tb.rdata),
    .rresp(tb.rresp),
    .rlast(tb.rlast),
    .ruser(tb.ruser),
    .rvalid(tb.rvalid),
    .rready(tb.rready)
  );

  // Drive TB tasks: positive first (should not fire), then negative (should fire)
  initial begin
    // AW channel
    tb.if_wa_channel_signals_are_stable_positive_case();
    tb.if_wa_channel_signals_are_unknown_positive_case();
    tb.if_wa_channel_valid_stable_positive_case();
    tb.if_wa_channel_signals_are_stable_negative_case();
    tb.if_wa_channel_signals_are_unknown_negative_case();
    tb.if_wa_channel_valid_stable_negative_case();

    // W channel
    tb.if_wd_channel_signals_are_stable_positive_case();
    tb.if_wd_channel_signals_are_unknown_positive_case();
    tb.if_wd_channel_valid_stable_positive_case();
    tb.if_wd_channel_signals_are_stable_negative_case();
    tb.if_wd_channel_signals_are_unknown_negative_case();
    tb.if_wd_channel_valid_stable_negative_case();

    // B channel
    tb.if_wr_channel_signals_are_stable_positive_case();
    tb.if_wr_channel_signals_are_unknown_positive_case();
    tb.if_wr_channel_valid_stable_positive_case();
    tb.if_wr_channel_signals_are_stable_negative_case();
    tb.if_wr_channel_signals_are_unknown_negative_case();
    tb.if_wr_channel_valid_stable_negative_case();

    // AR channel
    tb.if_ra_channel_signals_are_stable_positive_case();
    tb.if_ra_channel_signals_are_unknown_positive_case();
    tb.if_ra_channel_valid_stable_positive_case();
    tb.if_ra_channel_signals_are_stable_negative_case();
    tb.if_ra_channel_signals_are_unknown_negative_case();
    tb.if_ra_channel_valid_stable_negative_case();

    // R channel
    tb.if_rd_channel_signals_are_stable_positive_case();
    tb.if_rd_channel_signals_are_unknown_positive_case();
    tb.if_rd_channel_valid_stable_positive_case();
    tb.if_rd_channel_signals_are_stable_negative_case();
    tb.if_rd_channel_signals_are_unknown_negative_case();
    tb.if_rd_channel_valid_stable_negative_case();

    #100;
    $display("EVAL_DONE");
    $finish;
  end
endmodule

