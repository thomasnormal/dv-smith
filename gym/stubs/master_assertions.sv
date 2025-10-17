`ifndef MASTER_ASSERTIONS_INCLUDED_
`define MASTER_ASSERTIONS_INCLUDED_

// AXI4 master-side assertions stub
// Implement the required properties for all 5 channels (AW,W,B,AR,R)
// Follow the label naming exactly and include else-actions as shown below.

import axi4_globals_pkg::*;
import uvm_pkg::*; `include "uvm_macros.svh"

interface master_assertions (
  input                     aclk,
  input                     aresetn,
  // Write Address Channel Signals
  input               [3:0] awid,
  input [ADDRESS_WIDTH-1:0] awaddr,
  input               [3:0] awlen,
  input               [2:0] awsize,
  input               [1:0] awburst,
  input               [1:0] awlock,
  input               [3:0] awcache,
  input               [2:0] awprot,
  input                     awvalid,
  input                     awready,
  // Write Data Channel Signals
  input     [DATA_WIDTH-1:0] wdata,
  input [(DATA_WIDTH/8)-1:0] wstrb,
  input                      wlast,
  input                [3:0] wuser,
  input                      wvalid,
  input                      wready,
  // Write Response Channel
  input [3:0] bid,
  input [1:0] bresp,
  input [3:0] buser,
  input       bvalid,
  input       bready,
  // Read Address Channel Signals
  input               [3:0] arid,
  input [ADDRESS_WIDTH-1:0] araddr,
  input               [7:0] arlen,
  input               [2:0] arsize,
  input               [1:0] arburst,
  input               [1:0] arlock,
  input               [3:0] arcache,
  input               [2:0] arprot,
  input               [3:0] arqos,
  input               [3:0] arregion,
  input               [3:0] aruser,
  input                     arvalid,
  input                     arready,
  // Read Data Channel Signals
  input            [3:0] rid,
  input [DATA_WIDTH-1:0] rdata,
  input            [1:0] rresp,
  input                  rlast,
  input            [3:0] ruser,
  input                  rvalid,
  input                  rready
);

  initial begin
    `uvm_info("MASTER_ASSERTIONS","MASTER_ASSERTIONS stub active",UVM_LOW)
  end

  // Example (AW channel): All signals stable while AWVALID=1 and AWREADY=0
  // Replicate analogous properties for W,B,AR,R as required by the task YAML.
  property if_write_address_channel_signals_are_stable;
    @(posedge aclk) disable iff (!aresetn)
      (awvalid && !awready)
        |=> ($stable(awid) && $stable(awaddr) && $stable(awlen)
           && $stable(awsize) && $stable(awburst) && $stable(awlock)
           && $stable(awcache) && $stable(awprot));
  endproperty
  AXI_WA_STABLE_SIGNALS_CHECK: assert property (if_write_address_channel_signals_are_stable)
    else $error("ASSERT:AXI_WA_STABLE_SIGNALS_CHECK");

  // TODO: Implement remaining assertions with EXACT labels and else $error("ASSERT:<LABEL>"):
  // - AXI_WA_UNKNOWN_SIGNALS_CHECK
  // - AXI_WA_VALID_STABLE_CHECK
  // - AXI_WD_STABLE_SIGNALS_CHECK
  // - AXI_WD_UNKNOWN_SIGNALS_CHECK
  // - AXI_WD_VALID_STABLE_CHECK
  // - AXI_WR_STABLE_SIGNALS_CHECK
  // - AXI_WR_UNKNOWN_SIGNALS_CHECK
  // - AXI_WR_VALID_STABLE_CHECK
  // - AXI_RA_STABLE_SIGNALS_CHECK
  // - AXI_RA_UNKNOWN_SIGNALS_CHECK
  // - AXI_RA_VALID_STABLE_CHECK
  // - AXI_RD_STABLE_SIGNALS_CHECK
  // - AXI_RD_UNKNOWN_SIGNALS_CHECK
  // - AXI_RD_VALID_STABLE_CHECK

endinterface : master_assertions

`endif

