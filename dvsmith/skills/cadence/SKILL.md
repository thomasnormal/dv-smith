---
name: cadence
description: Comprehensive knowledge of Cadence EDA tools for digital design and verification. Covers Xcelium simulator (xrun), Incisive Metrics Center (IMC), JasperGold formal, Genus synthesis, Innovus P&R, and associated utilities. Includes command-line options, GUI usage, and best practices.
---

# Cadence EDA Tools

This skill provides comprehensive knowledge of Cadence EDA tools for digital design and verification workflows.

## Xcelium Simulator

### Basic Compilation and Simulation

#### Single-Step Mode (xrun)
```bash
# Basic simulation
xrun -sv -uvm design.sv testbench.sv

# With UVM
xrun -sv -uvm -uvmhome $UVM_HOME \
  -incdir src/includes \
  +incdir+src/tb \
  design.sv tb_top.sv \
  +UVM_TESTNAME=my_test

# Common options
xrun -64bit              # 64-bit mode
     -sv                 # SystemVerilog
     -v93                # VHDL-93
     -v200x              # VHDL-2008
     -uvm                # Enable UVM
     -ml                 # Mixed language
     -access +rwc        # Access for debug
     -timescale 1ns/1ps  # Time units
```

#### Multi-Step Mode

```bash
# 1. Compile
xmvlog -sv -64bit \
  -incdir includes \
  +define+DEBUG \
  design.sv

xmvhdl -v93 -64bit \
  design.vhd

# 2. Elaborate
xmelab -64bit \
  -access +rwc \
  -timescale 1ns/1ps \
  work.top_tb

# 3. Simulate
xmsim -64bit \
  -gui \
  work.top_tb:sv \
  +UVM_TESTNAME=test1
```

### Advanced xrun Options

```bash
# Coverage
xrun -coverage all \        # All coverage types
     -covoverwrite \        # Overwrite previous
     -covtest test1 \       # Test name
     -covfile cover.cfg     # Coverage config

# Assertions
xrun -assert             # Enable assertions
     -abv                # ABV mode
     -abvlib ieee_abv    # ABV library

# Debug
xrun -debug             # Full debug
     -linedebug          # Line debug
     -access +rwc        # Read/write/connectivity
     -gui                # Launch GUI

# Performance
xrun -turbo             # Turbo mode
     -parallel 4         # Parallel compilation
     -j 8                # Make jobs

# Waveforms
xrun -input @"database -open waves.shm -default"
     -input @"probe -create top_tb -all -depth all"
```

### Coverage Configuration

```tcl
# cover.cfg
set_coverage_options -type {branch expression toggle fsm assertion} \
                    -du_name /top/dut

set_coverage_exclude -du /top/dut/debug_logic
set_coverage_exclude -toggle -signal {reset test_mode}

# Merging coverage
set_coverage_merge -out merged.ucdb \
                   test1.ucdb test2.ucdb test3.ucdb
```

### SimVision GUI

#### TCL Commands
```tcl
# Open database
database -open waves.shm -default

# Create probes
probe -create top_tb -all -depth all
probe -create top_tb.dut -depth 2

# Run simulation
run 1000 ns
run -all

# Save/restore
preferences -save my_session.tcl
preferences -restore my_session.tcl

# Waveform operations
waveform new
waveform add top_tb.clk top_tb.reset
waveform format top_tb.data -radix hex
waveform zoom -fit

# Breakpoints
stop -create top_tb.state -value ERROR
stop -create -condition {top_tb.counter == 100}
```

#### Waveform Database

```bash
# SHM database (recommended)
xrun -input waves.tcl

# waves.tcl content:
database -open waves.shm -default -event
probe -create top_tb -all -memories -depth all
run
database -close

# VCD database
xrun -input @"$dumpfile(\"waves.vcd\"); $dumpvars(0, top_tb);"

# FSDB database (with Verdi)
xrun -loadpli debpli.so:novas_pli_boot \
     -input @"$fsdbDumpfile(\"waves.fsdb\"); $fsdbDumpvars(0, top_tb);"
```

## Incisive Metrics Center (IMC)

### Basic IMC Usage

```bash
# Launch IMC
imc &

# Command-line mode
imc -batch -exec analyze.tcl

# Load results
imc -load simulation.ucdb
```

### IMC TCL Commands

```tcl
# Load data
load -run run1 test1.ucdb
load -run run2 test2.ucdb

# Merge coverage
merge -out merged.ucdb -metrics all \
      -runs {run1 run2}

# Generate reports
report -summary -all -out coverage_summary.txt
report -detail -html -out coverage_report.html

# Analyze coverage
analyze -missing -type {branch toggle}
analyze -exclude uncovered.list

# Ranking and grading
rank -tests -metric all
grade -test test1
```

### Coverage Analysis

```tcl
# Set goals
set_goal -metric line 95
set_goal -metric branch 90
set_goal -metric toggle 80

# Exclusions
exclude -type branch -file excluded_branches.txt
exclude -instance top.dut.debug_*

# Refinement
refine -testname regression_* -out refined.ucdb

# Coverage models
model -type {line branch expression toggle fsm assertion}
```

## JasperGold Formal Verification

### Basic JasperGold Flow

```bash
# Launch JasperGold
jaspergold design.tcl

# Interactive mode
jaspergold
```

### JasperGold TCL Script

```tcl
# Clear previous
clear -all

# Analyze RTL
analyze -sv design.sv
analyze -vhdl design.vhd

# Elaborate
elaborate -top top_module \
          -param WIDTH=32 \
          -param DEPTH=256

# Clock and reset
clock clk
reset -expression {!rst_n}

# Assumptions
assume -env {request |-> ##[1:3] grant}
assume -env {!overflow}

# Assertions
assert -name NO_DEADLOCK {!deadlock}
assert -name DATA_INTEGRITY {data_out == expected_data}

# Prove
prove -all
prove -property {NO_DEADLOCK DATA_INTEGRITY}

# Coverage
cover -name FIFO_FULL {fifo_count == DEPTH}

# Run engines
set_engine_mode {B K I N}
set_prove_time_limit 3600
prove -bg -task proof_task
```

### Advanced Formal Techniques

```tcl
# Abstraction
abstract -memory mem_array
abstract -counter large_counter -min 0 -max 1000

# Constraints
constraint -add {mode inside {NORMAL, TEST}}
constraint -assume {!(a && b)}

# Bounded proof
prove -property PROP1 -bound 100

# Induction
prove -property PROP2 -induction

# Witness/counterexample
visualize -property PROP1 -vcd counter.vcd
visualize -show_path -format html

# Apps
check_deadlock
check_livelock
check_fsm -complete
check_x
```

## Genus Synthesis

### Basic Synthesis Flow

```tcl
# Read libraries
read_libs /tech/lib/slow.lib
read_physical_library /tech/lef/tech.lef

# Read design
read_hdl -sv {design.sv pkg.sv}
read_hdl -vhdl design.vhd

# Elaborate
elaborate top_module

# Constraints
read_sdc constraints.sdc
# or
create_clock -period 10 [get_ports clk]
set_input_delay -clock clk 2 [all_inputs]
set_output_delay -clock clk 3 [all_outputs]

# Synthesize
syn_gen
syn_map
syn_opt

# Reports
report_timing -nworst 10
report_power
report_area
report_qor

# Write output
write_hdl > netlist.v
write_sdc > out.sdc
write_design -innovus top_module
```

### Advanced Genus Options

```tcl
# Technology settings
set_db library_search_path {/tech/lib /tech/mem}
set_db init_lib_search_path $library_search_path
set_db use_scan_seqs_for_non_dft false

# Optimization
set_db syn_global_effort high
set_db opt_power_effort high
set_db retime true
set_db boundary_opto true

# DFT
define_dft shift_enable SE
define_dft test_mode TM
set_db dft_scan_style muxed_scan

# Low power
read_power_intent upf/design.upf
commit_power_intent
```

## Innovus Implementation

### Basic Innovus Flow

```tcl
# Initialize
init_design netlist.v top_module -floorplan floorplan.fp

# or from Genus
read_design top_module.invs

# Floorplan
floorPlan -site core_site \
          -r 1.0 0.7 10 10 10 10

# Power planning
globalNetConnect VDD -type pgpin -pin VDD -inst *
globalNetConnect VSS -type pgpin -pin VSS -inst *
addRing -nets {VDD VSS} -width 2 -spacing 1
addStripe -nets {VDD VSS} -width 1 -spacing 10

# Placement
place_opt_design

# CTS
create_ccopt_clock_tree_spec
ccopt_design

# Routing
routeDesign
optDesign -postRoute

# Verification
verify_connectivity
verify_geometry
verify_drc

# Output
defOut final.def
write_netlist final.v
```

### Advanced Innovus Commands

```tcl
# Multi-mode multi-corner
create_analysis_view -name slow_hot \
  -constraint_mode func_slow \
  -delay_corner slow_hot

set_analysis_view -setup {slow_hot} \
                 -hold {fast_cold}

# ECO
ecoDesign -cells eco_changes.tcl
ecoRoute

# SI analysis
setSIMode -num_si_iteration 5 \
         -delta_delay_threshold 5ps
optDesign -postRoute -si

# Power analysis
report_power -rail_analysis \
            -power_grid_library pg_lib
```

## Conformal Equivalence Checking

### Basic LEC Flow

```tcl
# Read libraries
read_library /tech/lib/tech.lib

# Read designs
read_design -golden rtl.v
read_design -revised netlist.v

# Match
match

# Verify
verify

# Report
report_verification_statistics
report_aborted_points
report_failing_points

# Debug
diagnose
analyze_abort -all
```

## Palladium Emulation

### Basic Commands

```bash
# Compile design
irun -compile_emulation design.sv

# Run emulation
palladiumrun -exec test.x \
            -cycles 1000000 \
            -database waves.shm
```

## VManager Verification Management

### Basic VManager Usage

```bash
# Create session
vmanager -create session.vsif

# Launch regression
vmanager -launch regression.vsif \
         -group nightly \
         -seed random

# Monitor
vmanager -monitor session_id
```

### VSIF File

```xml
<session>
  <group name="smoke">
    <test name="test1">
      <command>xrun -sv tb.sv +UVM_TESTNAME=test1</command>
    </test>
  </group>
  
  <group name="regression">
    <test name="test_random" count="100">
      <command>xrun -sv tb.sv +UVM_TESTNAME=test_random -seed auto</command>
    </test>
  </group>
</session>
```

## Indago Debug

### Basic Debug Flow

```bash
# Launch Indago
indago -db debug.db &

# Command-line debug
indago -tcl debug.tcl -db debug.db
```

### Debug Commands

```tcl
# Load database
open_db debug.db

# Set breakpoints
break -time 1000ns
break -condition {dut.state == ERROR}

# Watch variables
watch dut.counter
watch -change dut.fifo

# Trace
trace -back dut.error
trace -forward dut.request

# Smart log
smartlog -add "DUT" -severity INFO
smartlog -analyze
```

## Environment Setup

### Environment Variables

```bash
# Cadence installation
export CDS_INST_DIR=/tools/cadence/installs/INCISIVE
export PATH=$CDS_INST_DIR/bin:$PATH

# License
export CDS_LIC_FILE=5280@license_server
export LM_LICENSE_FILE=$CDS_LIC_FILE

# Work library
export WORKLIB=./work
export CDS_WORKLIB=$WORKLIB

# 64-bit mode
export CDS_AUTO_64BIT=ALL

# UVM
export UVM_HOME=$CDS_INST_DIR/tools/uvm/uvm_lib/uvm_sv
```

### Configuration Files

#### cds.lib
```
DEFINE worklib ./work
DEFINE ieee_lib $CDS_INST_DIR/tools/inca/files/IEEE
INCLUDE $CDS_INST_DIR/tools/inca/files/cds.lib
```

#### hdl.var
```
DEFINE WORK worklib
DEFINE SRC_ROOT ../src
INCLUDE $CDS_INST_DIR/tools/inca/files/hdl.var
```

## Best Practices

### Simulation
1. Use xrun single-step mode for simple designs
2. Enable appropriate access for debug (-access +rwc)
3. Use coverage configuration files
4. Separate compilation and elaboration for large designs
5. Use parallel compilation (-parallel)

### Coverage
1. Define clear coverage goals
2. Use exclusion files for unreachable code
3. Merge coverage incrementally
4. Review coverage regularly during development
5. Use IMC for coverage closure

### Formal
1. Start with simple properties
2. Use assumptions to constrain environment
3. Apply appropriate abstractions
4. Set reasonable proof bounds
5. Use different engines for different properties

### Synthesis
1. Use proper constraints (SDC)
2. Enable retiming for performance
3. Check QoR reports regularly
4. Use incremental synthesis for ECOs
5. Validate with formal equivalence

### Debug
1. Use appropriate database format (SHM recommended)
2. Limit probe depth for performance
3. Use smart logging for long simulations
4. Save debug sessions for reuse
5. Use Indago for complex debug scenarios

## Common Issues and Solutions

### Issue: License not available
```bash
# Check license status
lmstat -a -c $LM_LICENSE_FILE

# Use different feature
xrun -lic_queue
```

### Issue: Compilation errors
```bash
# Verbose compilation
xrun -v -messages

# Check log files
cat xrun.log
```

### Issue: Simulation too slow
```bash
# Use turbo mode
xrun -turbo

# Reduce access
xrun -access +r  # Read-only

# Disable assertions
xrun +noassert
```

### Issue: Coverage merge fails
```bash
# Check compatibility
imc -check test1.ucdb test2.ucdb

# Force merge
imc -merge -force -out merged.ucdb
```

### Issue: GUI not launching
```bash
# Check DISPLAY
export DISPLAY=:0

# Use console mode
xrun -tcl
```

## Tool Comparison

| Feature | Xcelium | VCS | Questa |
|---------|---------|-----|--------|
| Single-step | xrun | vcs | vsim |
| UVM support | Native | Native | Native |
| Mixed-language | Yes | Yes | Yes |
| Coverage | IMC | URG | UCDB |
| Debug | SimVision/Indago | DVE/Verdi | Visualizer |
| Formal | JasperGold | VC Formal | Questa Formal |
| Emulation | Palladium | Zebu | Veloce |

## References

- Cadence Xcelium User Guide
- SimVision User Guide
- IMC User Manual
- JasperGold Documentation
- Genus Synthesis Guide
- Innovus User Guide
- Cadence Online Support (support.cadence.com)
