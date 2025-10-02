Absolutely—here’s a curated list of open-source SystemVerilog/UVM test benches and VIPs similar to the `*_avip` repos you saw.

Quickly, a few more inside **mbits-mirafra** you may have missed: `i3c_avip`, `i2s_avip`, `spi_avip`, `axi4Lite_avip`, plus the already-there `axi4_avip` and `apb_avip`. ([GitHub][1])

### By protocol (outside mbits-mirafra)

**AHB**

* **YUU AHB Lite VIP** – Master & slave agents, UVM, MIT license. ([GitHub][2])
* **AHB2 VIP** – AMBA AHB 2.0 UVM VIP (Apache-2.0). ([GitHub][3])

**AXI / AXI-Lite**

* **TVIP-AXI** – Robust AXI4 / AXI4-Lite UVM VIP (master & slave agents), Apache-2.0. ([GitHub][4])
* **pulp-platform/axi** – AXI SystemVerilog IP **and** verification infrastructure used widely in academia/industry. ([GitHub][5])
* **uvm_axi4lite** – Lightweight AXI4-Lite UVM package (MIT). ([GitHub][6])

**APB**

* **APB VIP** – UVM VIP for APB (Apache-2.0). ([GitHub][7])
* **APB-UVM** – UVM environment for APB (MIT). ([GitHub][8])
* **AMBA_APB_SRAM** – APB v3 SRAM core + UVM TB (can serve as APB VIP), MIT license. ([GitHub][9])

**JTAG**

* **OpenTitan JTAG UVM Agent** – Production-grade agent and docs (used across many IP TBs). ([opentitan.org][10])
* **JTAG DMI Agent (OpenTitan)** – DMI monitor/RAL wrapped as an “agent.” Handy if you need RISC-V debug flows. ([opentitan.org][11])
* **jtag_vip_uvm** – Standalone JTAG VIP in UVM (GPL-2.0). ([GitHub][12])
* **pulp-platform/jtag_dpi** – SystemVerilog DPI JTAG model (useful to drive TBs via a remote debug bridge). ([GitHub][13])

**I²C / SPI / UART**

* **I2C VIP** – SystemVerilog UVM VIP with docs/testplan (Apache-2.0). ([GitHub][14])
* **SPI-Interface** – UVM TB verifying master/slave data transfer. ([GitHub][15])
* **UVM UART Example** – Simple host-side UVM agent bench for UART. ([GitHub][16])

**High-speed examples**

* **10G Ethernet MAC UVM TB** – Full UVM env for OpenCores XGE MAC. ([GitHub][17])
* **PCIe Transaction-Layer Verification** – SystemVerilog verification env for PCIe coursework (good starting point). ([GitHub][18])

### Notes

* **Licensing & maturity vary.** Many above are MIT/Apache (easy to adopt), a few are GPL or student projects—check the license and maintenance status before pulling them into a commercial flow. (Examples: TVIP-AXI is Apache-2.0; YUU AHB is MIT.) ([GitHub][4])
* **Tool support:** Modern Verilator builds have improved UVM features; there’s even public work showing **AXI UVM VIP** running under Verilator if you prefer an open simulator. ([antmicro.com][19])

If you want, I can filter this down to just (say) APB/JTAG with permissive licenses and active updates, or build a small matrix (protocol × agents × license × example tests) so you can pick quickly.

[1]: https://github.com/mbits-mirafra "mbits · GitHub"
[2]: https://github.com/seabeam/yuu_ahb "GitHub - seabeam/yuu_ahb: UVM AHB VIP"
[3]: https://github.com/GodelMachine/AHB2 "GitHub - GodelMachine/AHB2: AMBA AHB 2.0 VIP in SystemVerilog UVM"
[4]: https://github.com/taichi-ishitani/tvip-axi "GitHub - taichi-ishitani/tvip-axi: AMBA AXI VIP"
[5]: https://github.com/pulp-platform/axi "GitHub - pulp-platform/axi: AXI SystemVerilog synthesizable IP modules and verification infrastructure for high-performance on-chip communication"
[6]: https://github.com/smartfoxdata/uvm_axi4lite?utm_source=chatgpt.com "uvm_axi4lite is a uvm package for modeling ..."
[7]: https://github.com/muneebullashariff/apb_vip?utm_source=chatgpt.com "muneebullashariff/apb_vip: Verification IP for APB protocol"
[8]: https://github.com/cp024s/APB-UVM?utm_source=chatgpt.com "cp024s/APB-UVM: APB verification based on Universal ..."
[9]: https://github.com/courageheart/AMBA_APB_SRAM?utm_source=chatgpt.com "courageheart/AMBA_APB_SRAM"
[10]: https://opentitan.org/book/hw/dv/sv/jtag_agent/index.html "JTAG Agent - OpenTitan Documentation"
[11]: https://opentitan.org/book/hw/dv/sv/jtag_dmi_agent/index.html "JTAG DMI Agent - OpenTitan Documentation"
[12]: https://github.com/emmanouil-komninos/jtag_vip_uvm "GitHub - emmanouil-komninos/jtag_vip_uvm"
[13]: https://github.com/pulp-platform/jtag_dpi?utm_source=chatgpt.com "pulp-platform/jtag_dpi: JTAG DPI module for SystemVerilog ..."
[14]: https://github.com/muneebullashariff/i2c_vip "GitHub - muneebullashariff/i2c_vip: Verification IP for I2C protocol"
[15]: https://github.com/Anjali-287/SPI-Interface "GitHub - Anjali-287/SPI-Interface: UVM Testbench to verify serial transmission of data between SPI master and slave"
[16]: https://github.com/WeiChungWu/UVM_UART_Example "GitHub - WeiChungWu/UVM_UART_Example: An UVM example of UART"
[17]: https://github.com/andres-mancera/ethernet_10ge_mac_SV_UVM_tb "GitHub - andres-mancera/ethernet_10ge_mac_SV_UVM_tb: SystemVerilog-based UVM testbench for an Ethernet 10GE MAC core"
[18]: https://github.com/crusader2000/PCIE-Transaction-Layer-Verification "GitHub - crusader2000/PCIE-Transaction-Layer-Verification: PCIe System Verilog Verification Environment developed for PCIe course"
[19]: https://antmicro.com/blog/2024/09/open-source-uvm-verification-axi-in-verilator/?utm_source=chatgpt.com "Enabling open source UVM verification of AXI-based ..."

