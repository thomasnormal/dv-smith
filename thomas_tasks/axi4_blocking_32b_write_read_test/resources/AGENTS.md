# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an **Accelerated Verification IP (AVIP)** for the **AXI4 Protocol**, implementing a UVM-based testbench with HDL/HVL separation. The testbench is designed for both simulation and emulation, with synthesizable components (BFMs) pushed into the HDL top module and unsynthesizable components in the HVL top module.

## Build and Simulation Commands

**IMPORTANT**: All commands must be run from the `sim/cadence_sim` directory.

### Basic Workflow
```bash
cd sim/cadence_sim

# Step 1: Compilation (must be done first, and after any code changes)
make compile
# Example: make compile | tail -n 30

# Step 2: Run individual test
make simulate test=<test_name> uvm_verbosity=<VERBOSITY_LEVEL>
# Example: make simulate test=axi4_blocking_32b_write_read_test | tail -n 30

# Run regression (executes all tests in the list)
make regression testlist_name=<regression_testlist_name.list>
# Example: make regression testlist_name=axi4_transfers_regression.list | tail -n 30
```

After simulation, full uvm log files are saved in `<test_name>/<test_name>.log`
```
# Example: Search for errors/warnings
grep -E "UVM_ERROR|UVM_FATAL|UVM_WARNING" axi4_blocking_32b_write_read_test/axi4_blocking_32b_write_read_test.log
```

**Waveforms** are saved in `<test_name>/<test_name>.vcd`.

VCD files are plain ASCII text with ~3655 signals in a typical test. The `vcdcat` tool provides the fastest way to analyze waveforms without a GUI.

**Quick Start - Most Useful Commands:**

```bash
# Setup (required for vcdcat and Python vcdvcd)
export PYTHONPATH=~/.local/lib/python3.9/site-packages:$PYTHONPATH

# View complete AXI4 write transaction (all 3 channels) - Most Useful!
vcdcat -x <test_name>/<test_name>.vcd \
    hdl_top.intf.awvalid hdl_top.intf.awready \
    hdl_top.intf.wvalid hdl_top.intf.wready \
    hdl_top.intf.bvalid hdl_top.intf.bready | head -50

# Deltas mode - show ONLY signal changes (cleanest for debugging)
vcdcat -d -x <test_name>/<test_name>.vcd hdl_top.intf.awvalid hdl_top.intf.awready | head -30

# List interface signals only (filter 3655 signals down to ~40)
vcdcat -l <test_name>/<test_name>.vcd 'hdl_top.intf' | head -30

# View transaction data (addresses, IDs, data values)
vcdcat -x <test_name>/<test_name>.vcd \
    'hdl_top.intf.awaddr[31:0]' 'hdl_top.intf.awid[3:0]' \
    'hdl_top.intf.wdata[31:0]' 'hdl_top.intf.wstrb[3:0]' | head -40
```

**Key vcdcat Options:**
- `-x` : Exact match (essential with 3655 signals)
- `-d` : Deltas mode (show only changes - removes noise)
- `-l` : List signals only (find signal names)

To learn more about VCD analysis tools, see: `skills/VCD.md`

For more advanced waveform analysis (batch-mode automation, format conversion, selective probing), see: `skills/SIMVISION.md`

#### Coverage

**What is IMC?**
IMC (Incisive Metrics Center) is a *post-simulation analysis tool* - it only reads and analyzes coverage data that was already collected during simulation. It does NOT run any stimulus or simulations itself.

**Workflow:**
1. `make simulate` runs xrun with `-coverage all` → generates coverage database files (`.ucd`/`.ucm` in `cov_work/`)
2. `imc` loads those database files → analyzes/merges/reports coverage metrics
3. You identify gaps → write new tests → re-run `make simulate` → merge new coverage with IMC

**Viewing coverage results:**
```bash
# Load coverage database from a specific test run
# Note: This loads from cov_work/scope/<test_name>/ directory
imc -load <test_name> -execcmd "report -summary -metrics <functional|code>"

# Example:
imc -load axi4_claude_simple_test -execcmd "report -summary"
# name                                     Overall Average   ...
# -------------------------------------------------------------------------------- 
# uvm_pkg                                  n/a 
# |--uvm_test_top                          n/a 
# | |--axi4_env_h                          n/a 
# | | |--axi4_master_agent_h[0]            n/a
# | | | |--axi4_master_cov_h               26.78%
# | | |--axi4_slave_agent_h[0]             n/a  
# | | | |--axi4_slave_cov_h                26.78% 
# ...
```
More options: `-detail|-summary|-list, -text|-html, -metrics, -out, -covered|-uncovered|-excludes|-unr|-all|-both, -exclComments, -append, -showempty, -source, -assertionStatus, -allAssertionCounters, -aspect, -cumulative, -local, -grading, -cross, -kind,, -inst|-type,, -cubeExpand, entitynames`.

Export coverage to CSV for analysis/scripting. (Requires vmanager is installed):
```bash
imc -load axi4_claude_simple_test -execcmd "csv_export -out coverage.csv -overwrite"
column -t -s',' coverage.csv | head -n 30
```

**Regression coverage:**

When you run `make regression testlist_name=<file.list>`, it creates **separate coverage databases** for each test in `cov_work/scope/`:
- Each test gets its own directory: `cov_work/scope/<test_name>_<timestamp>/`
- Coverage is NOT automatically merged

To get total regression coverage, you must manually merge:
```bash
# Merge all test coverage and generate text report
imc -batch << EOF
merge cov_work/scope/*_test* -overwrite -out merged_coverage
load -run merged_coverage
report -summary -out regression_summary.txt
csv_export -out regression_coverage.csv -overwrite
exit
EOF

# Then view the text report or analyze CSV
cat regression_summary.txt
```

**Analyzing Coverage Gaps:**
```bash
# Export coverage to CSV for analysis
imc -load <test_name> -execcmd "csv_export -out coverage.csv -overwrite"

# Find items below 50% coverage
awk -F',' 'NR>1 && $5 ~ /[0-9]/ && $5+0 < 50 {print $4 ": " $5}' coverage.csv | head -20

# Sort by coverage (lowest first) to prioritize work
tail -n +2 coverage.csv | awk -F',' '$5 ~ /[0-9]/ {print $5 "\t" $4}' | sort -n | head -20

# Search for specific coverpoint
grep "AWLEN_CP" coverage.csv

# Get hierarchical table view (like report -summary)
imc -load <test_name> -execcmd "report -summary hdl_top..."

# Or view CSV as formatted table
column -t -s',' coverage.csv | less
```

To learn more about IMC (batch mode, refinements, CSV analysis, tree views, advanced features), see `skills/IMC.md`

### Clean Up
```bash
# Clean compilation artifacts (removes xcelium.d/, *.log, *.history)
make clean_compile

# Clean simulation artifacts (removes *Test directories and cov_work)
# NOTE: This removes directories ending in capital 'Test', not lowercase 'test'
make clean_simulate

# To remove test result directories manually:
rm -rf axi4_*test
```

### Default Values

- **test**: `axi4_base_test` (if not specified)
- **uvm_verbosity**: `UVM_MEDIUM` (if not specified)
  - Options: UVM_NONE, UVM_LOW, UVM_MEDIUM, UVM_HIGH, UVM_FULL, UVM_DEBUG
- **seed**: `random` (if not specified)
- **test_folder**: Same as test name (creates directory for test outputs)

### Gotchas

1. **Must compile before simulate**: Always run `make compile` after code changes before running tests
2. **Run from correct directory**: Commands must be executed from `sim/cadence_sim/`
3. **Test directories persist**: `make clean_simulate` removes `*Test` (capital T) but test result directories use lowercase `test` and persist. Remove manually if needed.
4. **VCD location**: Waveform VCD files are moved into the test directory automatically
5. **Coverage**: Coverage data is stored in `cov_work/scope/<test_name>/`

## Architecture

### HDL/HVL Split Architecture

The testbench uses an accelerated verification approach with strict HDL/HVL separation:

- **HDL Top** (`src/hdl_top/hdl_top.sv`): Contains synthesizable components
  - Clock generation: 20ns period (toggling every 10ns)
  - Active-low reset generation
  - AXI4 interface (`axi4_if.sv`)
  - Master and Slave BFMs (Bus Functional Models)
  - SVA Assertions
  - VCD waveform dumping (`$dumpfile` and `$dumpvars`)

- **HVL Top** (`src/hvl_top/hvl_top.sv`): Contains UVM testbench components
  - Test classes
  - Environment with agents, sequencers, drivers, monitors
  - Sequences and sequence items
  - Virtual sequencer
  - Scoreboard
  - Coverage collectors

### Component Hierarchy

```
axi4_env
├── axi4_master_agent[] (configurable array, default 1 master)
│   ├── axi4_master_driver_proxy (HVL - connects to BFM)
│   ├── axi4_master_monitor_proxy (HVL - connects to BFM)
│   ├── axi4_master_write_sequencer
│   ├── axi4_master_read_sequencer
│   └── axi4_master_coverage
├── axi4_slave_agent[] (configurable array, default 1 slave)
│   ├── axi4_slave_driver_proxy (HVL - connects to BFM)
│   ├── axi4_slave_monitor_proxy (HVL - connects to BFM)
│   ├── axi4_slave_write_sequencer
│   ├── axi4_slave_read_sequencer
│   └── axi4_slave_coverage
├── axi4_virtual_sequencer (coordinates master/slave sequences)
└── axi4_scoreboard (compares master/slave transactions)
```

### BFM Architecture (HDL Top)

The BFMs in HDL top instantiate parametrically:
```systemverilog
genvar i;
generate
  for (i=0; i<NO_OF_MASTERS; i++) begin : axi4_master_agent_bfm
    axi4_master_agent_bfm #(.MASTER_ID(i)) axi4_master_agent_bfm_h(intf);
  end
  for (i=0; i<NO_OF_SLAVES; i++) begin : axi4_slave_agent_bfm
    axi4_slave_agent_bfm #(.SLAVE_ID(i)) axi4_slave_agent_bfm_h(intf);
  end
endgenerate
```

Each agent BFM contains:
- Driver BFM: Interface with tasks for driving protocol signals
- Monitor BFM: Interface for sampling and observing transactions

### Key Packages

- `axi4_globals_pkg`: Global parameters, enums, structs
- `axi4_master_pkg`: Master agent components
- `axi4_slave_pkg`: Slave agent components
- `axi4_env_pkg`: Environment and configuration classes
- `axi4_test_pkg`: Test classes
- `axi4_master_seq_pkg` / `axi4_slave_seq_pkg`: Sequence libraries
- `axi4_virtual_seq_pkg`: Virtual sequences (coordinate master/slave)

### Configuration Parameters (axi4_globals_pkg.sv)

```systemverilog
parameter int NO_OF_MASTERS = 1;              // Number of master agents
parameter int NO_OF_SLAVES = 1;               // Number of slave agents
parameter int ADDRESS_WIDTH = 32;             // Address bus width
parameter int DATA_WIDTH = 32;                // Data bus width (via macro)
parameter int SLAVE_MEMORY_SIZE = 12;         // Slave memory size in KB
parameter int SLAVE_MEMORY_GAP = 2;           // Memory gap size
parameter int OUTSTANDING_FIFO_DEPTH = 16;    // Outstanding transaction depth
parameter int STROBE_WIDTH = (DATA_WIDTH/8);  // Write strobe width
parameter int LENGTH = 8;                     // Address channel length
```

## Test Structure

### Test Location
All tests are in `src/hvl_top/test/`. Test names listed in `src/hvl_top/testlists/axi4_transfers_regression.list`.

### Base Test (`axi4_base_test.sv`)
All tests extend from `axi4_base_test` which:
- Creates the environment configuration
- Sets up master and slave agent configurations
- Instantiates the environment with scoreboard and virtual sequencer
- Configures address ranges, transfer modes, and response modes

### Test Structure Pattern

Every test follows this pattern:

```systemverilog
class axi4_<feature>_test extends axi4_base_test;
  `uvm_component_utils(axi4_<feature>_test)

  // Declare virtual sequence handle
  axi4_virtual_<feature>_seq axi4_virtual_<feature>_seq_h;

  extern function new(string name, uvm_component parent);
  extern virtual task run_phase(uvm_phase phase);
endclass

task axi4_<feature>_test::run_phase(uvm_phase phase);
  axi4_virtual_<feature>_seq_h = axi4_virtual_<feature>_seq::type_id::create(...);

  phase.raise_objection(this);  // Prevent simulation from ending
  axi4_virtual_<feature>_seq_h.start(axi4_env_h.axi4_virtual_seqr_h);
  phase.drop_objection(this);   // Allow simulation to end
endtask
```

### Virtual Sequence Pattern

Virtual sequences coordinate master and slave sequences:

```systemverilog
task axi4_virtual_<feature>_seq::body();
  // Create sequence instances
  axi4_master_write_seq_h = axi4_master_write_seq::type_id::create(...);
  axi4_slave_write_seq_h = axi4_slave_write_seq::type_id::create(...);

  // Start slave sequences in background (forever loops)
  fork
    begin : SLAVE_WRITE
      forever begin
        axi4_slave_write_seq_h.start(p_sequencer.axi4_slave_write_seqr_h);
      end
    end
  join_none

  // Start master sequences (actual test stimulus)
  fork
    begin: MASTER_WRITE
      repeat(N) begin
        axi4_master_write_seq_h.start(p_sequencer.axi4_master_write_seqr_h);
      end
    end
  join
endtask
```

## Adding a New Test

### Step-by-Step Process

1. **Create test file** in `src/hvl_top/test/axi4_<your_test>_test.sv`:

```systemverilog
`ifndef AXI4_YOUR_TEST_INCLUDED_
`define AXI4_YOUR_TEST_INCLUDED_

class axi4_your_test extends axi4_base_test;
  `uvm_component_utils(axi4_your_test)

  axi4_virtual_<suitable>_seq axi4_virtual_seq_h;

  extern function new(string name = "axi4_your_test", uvm_component parent = null);
  extern virtual task run_phase(uvm_phase phase);
endclass : axi4_your_test

function axi4_your_test::new(string name = "axi4_your_test", uvm_component parent = null);
  super.new(name, parent);
endfunction : new

task axi4_your_test::run_phase(uvm_phase phase);
  axi4_virtual_seq_h = axi4_virtual_<suitable>_seq::type_id::create("axi4_virtual_seq_h");
  `uvm_info(get_type_name(),$sformatf("Running your test"),UVM_LOW);

  phase.raise_objection(this);
  axi4_virtual_seq_h.start(axi4_env_h.axi4_virtual_seqr_h);
  phase.drop_objection(this);
endtask : run_phase

`endif
```

2. **Add to test package** `src/hvl_top/test/axi4_test_pkg.sv`:

```systemverilog
  `include "axi4_your_test.sv"
```

3. **Compile**:

```bash
cd sim/cadence_sim
make clean_compile
make compile
```

4. **Run test**:

```bash
make simulate test=axi4_your_test
```

5. **Optional: Add to regression** in `src/hvl_top/testlists/<list>.list`:

```
axi4_your_test
```

## Coding Guidelines

### Naming Conventions (from coding_guidelines.md)

1. **Line length**: Restrict code to 100 characters
2. **Case**: Use lowercase with underscores: `axi_fabric_scoreboard_error`
3. **Suffixes/Prefixes**:
   - `_t`: Typedef'd type
   - `_e`: Enumerated type
   - `_h`: Class handle
   - `_m`: Protected class member
   - `_cfg`: Configuration object handle
   - `_ap`: Analysis port handle
   - `_group`: Covergroup handle
4. **Structs/Unions/Enums**:
   - Structs end with `_s`: `axi4_write_transfer_char_s`
   - Unions end with `_u`
   - Enums end with `_e` with UPPERCASE values: `WRITE_INCR`
5. **Control structures**: Always use `begin-end` pairs
6. **Closing identifiers**: Always use labels: `endfunction: name`, `endclass: axi4_env`
7. **One class per file**: Keep filename same as class name
8. **Randomization**: Always check success with `if()` not `assert`:

```systemverilog
if(!seq_item.randomize() with {address inside {[0:32'hF000_FC00]};}) begin
  `uvm_error("seq_name","randomization failure, please check constraints")
end
```

9. **$cast()**: Always check success:

```systemverilog
if(!$cast(t, to_be_cloned.clone())) begin
  `uvm_error("get_a_clone","$cast failed for to_be_cloned")
end
```

10. **Methods**: Declare as `extern` and `virtual`
11. **No hard-coded values**: Use constants/parameters
12. **Use `if` not `assert`** for checking method call status
13. **No `#0` delays**: Use non-blocking assignments (`<=`) instead
14. **No associative arrays with `[*]`**: Use `[int]` or `[string]` instead

## File Organization

```
src/
├── globals/                    # Global package
│   └── axi4_globals_pkg.sv
├── hdl_top/                    # Synthesizable HDL
│   ├── axi4_interface/axi4_if.sv
│   ├── master_agent_bfm/       # Master BFMs
│   │   ├── axi4_master_driver_bfm.sv
│   │   ├── axi4_master_monitor_bfm.sv
│   │   └── axi4_master_agent_bfm.sv (wrapper)
│   ├── slave_agent_bfm/        # Slave BFMs
│   ├── *_assertions.sv         # SVA assertions
│   └── hdl_top.sv
└── hvl_top/                    # UVM testbench
    ├── master/                 # Master UVM components
    ├── slave/                  # Slave UVM components
    ├── env/                    # Environment, scoreboard
    ├── test/                   # Test classes
    │   ├── axi4_base_test.sv
    │   ├── axi4_test_pkg.sv (includes all tests)
    │   ├── sequences/          # Master/slave sequences
    │   │   ├── master_sequences/
    │   │   └── slave_sequences/
    │   ├── virtual_sequences/  # Virtual sequences
    │   └── testlists/          # Regression lists
    └── hvl_top.sv

sim/
├── cadence_sim/                # Working directory
│   ├── makefile
│   └── regression_handling.py
└── axi4_compile.f              # Compilation file list

doc/                            # PDFs (architecture, user guide)
```

## Key Concepts

### Proxy Pattern (HVL ↔ HDL Communication)

The testbench uses "proxy" components in HVL that communicate with BFMs in HDL:

- **Driver Proxy (HVL)** → calls tasks in **Driver BFM (HDL)**
- **Monitor BFM (HDL)** → sends transactions to **Monitor Proxy (HVL)**

This allows HVL to remain unsynthesizable (classes, dynamic memory) while HDL is synthesizable (interfaces, tasks).

### Virtual Sequencer

Coordinates multiple sequencers:
- Has handles to all master/slave sequencers
- Virtual sequences run on virtual sequencer
- Can start sequences on any agent's sequencer via `p_sequencer.<seqr_handle>`

### Scoreboard

Compares transactions between master and slave:
- Receives transactions via analysis ports
- Stores in FIFOs
- Compares signals (awid, awaddr, wdata, etc.)
- Reports mismatches as UVM_ERROR

## Debugging

### Log Files

Location: `<test_name>/<test_name>.log`

See previous section on waveforms and coverage.

### Common Issues

1. **Test not found**: Did you add `\`include` to `axi4_test_pkg.sv`?
2. **Compilation errors**: Did you run `make clean_compile` before `make compile`?
3. **UVM_FATAL on timeout**: Objections not balanced (missing `drop_objection`)
4. **Scoreboard errors**: Master/slave not synchronized (check slave sequences running)

## VIP Features

This AXI4 VIP supports:
- Independent read/write channels with separate sequencers
- Blocking and non-blocking transfers
- Parallel write and read transfers
- Outstanding transactions (configurable depth)
- Burst types: FIXED, INCR, WRAP
- Response types: OKAY, EXOKAY, SLVERR, DECERR
- Out-of-order transactions
- Quality of Service (QoS)
- Unaligned address transfers
- Custom slave memory (8-bit storage)
- Narrow transfers (8b/16b/32b/64b)
- Lock access (normal/exclusive)
- Cache/Protection/Region attributes
