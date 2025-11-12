# Terminal Bench Task Creation Procedure

This document describes the complete procedure for creating a new terminal bench task based on an existing UVM testbench. This procedure consolidates lessons learned from creating `axi4_blocking_wrap_burst_write_read_test`, `axi4_blocking_incr_burst_read_test`, and `axi4_blocking_incr_burst_write_read_test`.

## Prerequisites

- Access to the AXI4 testbench repository at `~/axi4_avip/`
- Cadence tools (xrun, imc) installed and licensed
- Terminal Bench CLI (`tb`) installed
- Working directory: `/home/thomas-ahle/dv-smith/thomas_tasks/`

## Overview

The procedure involves three main phases:
1. **Analysis Phase**: Examine existing test files and gather coverage data
2. **Creation Phase**: Create task directory structure and configuration files
3. **Validation Phase**: Iteratively test and fix until oracle agent achieves 100% accuracy

---

## Phase 1: Analysis Phase

### Step 1.1: Select a Test File

Browse the testbench to find an appropriate test file to base your task on.

```bash
ls ~/axi4_avip/src/hvl_top/test/
```

**Selection criteria:**
- Test should exercise specific, well-defined functionality
- Test should have clear coverage requirements
- Test complexity should be appropriate for your target difficulty level
- Test should be different from existing tasks

**Example:**
```bash
# Selected: axi4_blocking_wrap_burst_write_read_test.sv
# Rationale: Tests WRAP burst type, has clear coverage bins, moderate complexity
```

### Step 1.2: Examine Test Structure

Read the selected test file to understand its structure:

```bash
cat ~/axi4_avip/src/hvl_top/test/axi4_blocking_wrap_burst_write_read_test.sv
```

**Key elements to identify:**
- Base class (e.g., `axi4_base_test`)
- Virtual sequence being started
- Number and types of transactions
- Any special configuration (e.g., `ONLY_READ_DATA` mode)
- UVM component registration

**Example findings:**
```systemverilog
class axi4_blocking_wrap_burst_write_read_test extends axi4_base_test;
  `uvm_component_utils(axi4_blocking_wrap_burst_write_read_test)

  axi4_virtual_bk_wrap_burst_write_read_seq axi4_virtual_seq_h;

  function void setup_axi4_env_cfg();
    super.setup_axi4_env_cfg();
    // Default mode: READ_WRITE_DATA (no special config needed)
  endfunction
endclass
```

### Step 1.3: Examine Virtual Sequence

Locate and read the virtual sequence file:

```bash
# Find the virtual sequence directory
ls ~/axi4_avip/src/hvl_top/test/virtual_sequences/

# Read the virtual sequence
cat ~/axi4_avip/src/hvl_top/test/virtual_sequences/axi4_virtual_bk_wrap_burst_write_read_seq.sv
```

**Key elements to identify:**
- Master sequences being started
- Slave sequences being started
- Transaction counts (e.g., 2 writes, 3 reads)
- Sequence parameters and constraints
- Fork/join structure

**Example findings:**
```systemverilog
fork
  forever begin
    axi4_slave_wr_seq.start(p_sequencer.axi4_slave_write_seqr_h);
  end
join_none

fork
  forever begin
    axi4_slave_rd_seq.start(p_sequencer.axi4_slave_read_seqr_h);
  end
join_none

repeat(2) begin
  axi4_master_write_seq.start(p_sequencer.axi4_master_write_seqr_h);
end

repeat(3) begin
  axi4_master_read_seq.start(p_sequencer.axi4_master_read_seqr_h);
end
```

### Step 1.4: Examine Master Sequences

Locate and read the master sequence files:

```bash
ls ~/axi4_avip/src/hvl_top/test/sequences/master_sequences/

# Read write sequence
cat ~/axi4_avip/src/hvl_top/test/sequences/master_sequences/axi4_master_bk_write_wrap_burst_seq.sv

# Read read sequence
cat ~/axi4_avip/src/hvl_top/test/sequences/master_sequences/axi4_master_bk_read_wrap_burst_seq.sv
```

**Key elements to identify:**
- Transaction constraints (e.g., `awsize`, `awburst`, `arsize`, `arburst`)
- Transfer types (BLOCKING vs NON_BLOCKING)
- Randomization patterns

**CRITICAL OBSERVATION:** Check which parameters are FIXED vs RANDOM:
```systemverilog
// Example: INCR burst read sequence
if(!req.randomize() with {
  req.arsize == READ_4_BYTES;      // FIXED - must require in coverage
  req.tx_type == READ;              // FIXED - must require in coverage
  req.arburst == READ_INCR;         // FIXED - must require in coverage
  req.transfer_type == BLOCKING_READ; // FIXED - must require in coverage
  // NOTE: arlen is NOT constrained - it's RANDOM, don't require specific values!
}) begin
  `uvm_fatal("axi4","Rand failed");
end
```

**Key principle:** Only require coverage bins for parameters that are FIXED by constraints. Don't require random/unconstrained values.

### Step 1.5: Run Simulation and Get Coverage

Compile and simulate the original test to gather coverage data:

```bash
cd ~/axi4_avip/sim/cadence_sim

# Compile
make compile

# Simulate
make simulate test=axi4_blocking_wrap_burst_write_read_test

# Get coverage summary
imc -load axi4_blocking_wrap_burst_write_read_test -execcmd "report -summary"

# Get detailed coverage (for exact bin names)
imc -load axi4_blocking_wrap_burst_write_read_test -execcmd "report -detail -covered"
```

**CRITICAL: Note the coverage database location**
- Database is at: `cov_work/scope/<test_name>`
- NOT at: `cov_work/scope/<test_name>/<test_name>` (the name is not repeated)

**Document the following:**
- Coverage group names (e.g., `AWSIZE_CP`, `AWBURST_CP`, `ARSIZE_CP`, `ARBURST_CP`)
- Bin names (e.g., `AWSIZE_2BYTES`, `READ_WRAP`, `ARSIZE_4BYTES`)
- Coverage percentages achieved by the original test
- Simulation time and performance metrics

**Important:** Use the exact bin names from the coverage report, not assumed names. For example, in this case the WRAP burst type bin was named `READ_WRAP` for both read and write channels, not `WRITE_WRAP` or `AWBURST_WRAP`.

---

## Phase 2: Creation Phase

### Step 2.1: Create Task Directory Structure

```bash
cd /home/thomas-ahle/dv-smith/thomas_tasks

# Create main task directory (use the same name as the test file without .sv)
mkdir -p axi4_blocking_wrap_burst_write_read_test

# Create subdirectories
mkdir -p axi4_blocking_wrap_burst_write_read_test/resources
mkdir -p axi4_blocking_wrap_burst_write_read_test/tests
```

**Directory structure:**
```
axi4_blocking_wrap_burst_write_read_test/
├── Dockerfile
├── docker-compose.yaml
├── run-tests.sh
├── solution.sh
├── task.yaml
├── resources/
│   ├── AGENTS.md
│   ├── clean_repo.sh
│   └── coverage_requirements.txt
└── tests/
    ├── test_outputs.py
    └── standard_grader.py
```

### Step 2.2: Create Dockerfile

Create `axi4_blocking_incr_burst_write_read_test/Dockerfile`:

```dockerfile
# RockyLinux 9 has /bin/sh symlinked to bash, unlike Ubuntu where /bin/sh is dash.
# This is important for Cadence tools that expect /bin/sh to be bash.
FROM rockylinux:9

# Install system packages and Python tools in one layer
# First install EPEL and enable CRB repo (needed for bat, miller, parallel)
RUN dnf -y --setopt=install_weak_deps=False --setopt=tsflags=nodocs install epel-release dnf-plugins-core \
    && dnf config-manager --set-enabled crb \
    && dnf -y --setopt=install_weak_deps=False --setopt=tsflags=nodocs --nobest install \
      python3.12 python3.12-pip \
      which git make tmux \
      tcsh ksh libnsl libxcrypt-compat \
      fzf bat miller parallel \
    && dnf clean all \
    && rm -rf /var/cache/dnf \
    && python3.12 -m pip install --no-cache-dir pytest vcdvcd yq \
    && ln -sf /lib64/ld-linux-x86-64.so.2 /lib64/ld-lsb-x86-64.so.3

# The last line, copying ld-linux is some cadence thing.
# Cadence environment and test configuration
ENV PATH="/opt/cadence/installs/XCELIUM2403/bin:\
/opt/cadence/installs/XCELIUM2403/tools/bin/64bit:\
/opt/cadence/installs/VMANAGER2403/bin:\
${PATH}" \
    TB_HOME=/axi4_avip \
    TEST_NAME=student_example_incr_burst_write_read_test

# Clone and prepare repository
RUN git clone --depth=1 https://github.com/mbits-mirafra/axi4_avip.git /axi4_avip

# Copy only the clean_repo script and non-solution resources
COPY resources/clean_repo.sh /tmp/clean_repo.sh
COPY resources/coverage_requirements.txt /resources/coverage_requirements.txt
COPY resources/AGENTS.md /resources/AGENTS.md

# Setup repository and create directories in one layer
RUN bash /tmp/clean_repo.sh \
    && rm /tmp/clean_repo.sh \
    && mkdir -p /tests /oracle \
    && chown -R 1000:1000 /axi4_avip /tests /resources

# Smoke test - verify critical tools are accessible
# TRIAGE tools: fzf (fuzzy finder), bat (syntax viewer), yq (YAML), mlr (CSV), parallel
CMD ["bash", "-c", "\
  xrun -version \
  && imc -help \
  && which make \
  && which python3.12 \
  && which tmux \
  && which fzf \
  && which bat \
  && which yq \
  && which mlr \
  && which parallel \
  && which vcdcat \
  && which python -c 'import vcdvcd' \
  && echo 'All tools verified'"]
```

**Key points:**
- Use RockyLinux 9 (Cadence tools expect /bin/sh to be bash)
- Combine system package installation in one layer for efficiency
- **CRITICAL:** Clone repository during build, don't mount it
- **CRITICAL:** COPY resources during build, don't mount them
- **CRITICAL:** Set Cadence tools PATH in ENV, not docker-compose
- Run clean_repo.sh during build to prepare exam environment
- Install triage tools (fzf, bat, yq, mlr, parallel) for debugging
- Clean up caches in same layer to minimize image size
- Use `--depth=1` for faster git clone
- **DO NOT include `user: "1000:1000"` in build stage!** (add chown after build)

**Common issues:**
- `vcdvcd==2.3.3` has unavailable dependency - use latest `vcdvcd`
- Forgetting to set PATH will cause "command not found" for xrun/imc
- Mounting repo as volume instead of cloning defeats the purpose of clean_repo.sh

### Step 2.3: Create docker-compose.yaml

Create `axi4_blocking_incr_burst_write_read_test/docker-compose.yaml`:

```yaml
services:
  client:
    build:
      dockerfile: Dockerfile
    image: ${T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME}
    container_name: ${T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME}
    command: [ "sh", "-c", "sleep infinity" ]
    init: true  # use tini to handle zombie processes
    extra_hosts:
      - "hardware.normalcomputing.net:10.4.120.82"
    environment:
      - CDS_LIC_FILE=5280@10.4.120.82
      - LM_LICENSE_FILE=5280@10.4.120.82
      - SIM_SCRATCH=/dev/shm/sim_scratch
      - XCELIUM_CACHE=/xcelium_cache
      - TB_HOME=/axi4_avip
      - TEST_NAME=student_example_incr_burst_write_read_test
    volumes:
      - /opt/cadence/installs:/opt/cadence/installs
      - /dev/shm/sim_scratch:/dev/shm/sim_scratch
      - /var/lib/xcelium_cache:/xcelium_cache
      - ${T_BENCH_TASK_LOGS_PATH}:${T_BENCH_CONTAINER_LOGS_PATH}
      - ${T_BENCH_TASK_AGENT_LOGS_PATH}:${T_BENCH_CONTAINER_AGENT_LOGS_PATH}
```

**CRITICAL: DO NOT ADD THIS LINE:**
```yaml
    user: "1000:1000"    # ❌ NEVER ADD THIS - breaks agent installation!
```

**Why?** The claude-code agent needs root permissions to:
- Create `/installed-agent` directory
- Run `apt-get install` commands
- Install Node.js via nvm
- Install npm packages globally

**Key points:**
- **DO NOT mount the repository** - it's cloned in Dockerfile
- **DO NOT mount resources** - they're copied in Dockerfile
- **DO NOT set PATH here** - it's set in Dockerfile ENV
- Mount only:
  - Cadence tool installation directory (read-only access)
  - Shared memory for simulation scratch space
  - Xcelium cache directory
  - Terminal Bench log directories (managed by framework)
- Use `init: true` to handle zombie processes with tini
- Set license server environment variables
- Add extra_hosts for license server DNS resolution
- Command is `sleep infinity` - Terminal Bench will exec commands as needed

**What NOT to include:**
- Repository volume mount (defeats clean_repo.sh)
- Resources volume mount (defeats resource copying)
- PATH in environment (should be in Dockerfile)
- Working directory (Terminal Bench manages this)
- Custom command (Terminal Bench manages execution)
- `user: "1000:1000"` specification

### Step 2.4: Create task.yaml

Create `axi4_blocking_wrap_burst_write_read_test/task.yaml` with clear, detailed instructions for AI agents. Include:

- Environment context
- Exact task requirements
- Transaction specifications (counts, sizes, types)
- Grading criteria with percentages
- Helpful hints without giving away the solution

**Template:**
```yaml
instruction: |-
  You are given access to a UVM-based AXI4 testbench environment.
  Read AGENTS.md for details on how to work the testbench.

  Task: Write a UVM test called axi4_blocking_wrap_burst_write_read_test
  that performs AXI4 write and read transactions with WRAP burst type.

  ### Write Transactions (2 transactions):
  - Transfer size: 2 bytes (AWSIZE=1 for 16-bit transfers)
  - Burst type: WRAP (AWBURST=2)

  ### Read Transactions (3 transactions):
  - Transfer size: 4 bytes (ARSIZE=2 for 32-bit transfers)
  - Burst type: WRAP (ARBURST=2)

  ### General Requirements:
  - The test should perform BLOCKING transfers (not non-blocking)
  - Use WRAP burst type for all transactions
  - Ensure proper handshaking on all AXI4 channels

  ## Grading

  Your test will be graded based on three criteria:

  ### Scoreboard Validation (40%)
  - No UVM_ERROR or UVM_FATAL messages in simulation
  - All transactions complete successfully

  ### Functional Coverage (50%)
  - Write channel coverage bins:
    - AWSIZE_2BYTES (2-byte transfer size)
    - AWBURST_CP -> READ_WRAP (WRAP burst type)
  - Read channel coverage bins:
    - ARSIZE_4BYTES (4-byte transfer size)
    - ARBURST_CP -> READ_WRAP (WRAP burst type)

  ### Performance (10%)
  - Simulation efficiency (coverage achieved per microsecond of sim time)

  ## Hints
  1. Extend from `axi4_base_test`
  2. Create a virtual sequence that starts master and slave sequences
  3. Use blocking write and read sequences for both master and slave
  4. The master sequence should constrain transactions to use WRAP burst type
  5. Run the write sequence 2 times and read sequence 3 times
  6. Start the slave sequences in `fork/join_none` to handle responses
  7. Make sure to raise and drop objections appropriately

author_name: DV Smith
author_email: thomas@normal-computing.ai
difficulty: easy
category: verification-engineering
tags:
  - coding
  - verification
  - axi4
  - blocking-transactions
  - wrap-burst
parser:
  - pytest
max_agent_timeout_sec: 900.0
max_test_timeout_sec: 240.0
run_tests_in_same_shell: false
disable_asciinema: true
estimated_duration_sec: 600
expert_time_estimate_min: 10
junior_time_estimate_min: 30
```

**Key points for writing good instructions:**
- Be specific about what needs to be created (exact test class name)
- List transaction requirements clearly (counts, sizes, types)
- Mention blocking vs non-blocking
- Reference AGENTS.md for testbench details
- Include grading criteria breakdown with percentages
- Provide hints about base classes, sequences, and patterns
- **Match coverage requirements in instruction to coverage_requirements.txt**
- **TEST_NAME MUST BE CONSISTENT** across Dockerfile, docker-compose.yaml, task.yaml, and solution.sh

### Step 2.5: Create solution.sh

Create `axi4_blocking_incr_burst_write_read_test/solution.sh`:

This script should create all the files needed for a complete solution. Based on your analysis from Phase 1, create:

1. **Master write sequence** (if not using existing production sequences)
2. **Master read sequence** (if not using existing production sequences)
3. **Virtual sequence**
4. **Test class**
5. **Update package files**

The script should:
- Use heredocs to create multi-line SystemVerilog files
- Follow UVM coding standards
- Include proper class registration with `uvm_object_utils` or `uvm_component_utils`
- Implement required methods (new(), build_phase(), run_phase(), body())
- Raise and drop objections in the test's run_phase
- Start slave sequences in forever loops with fork/join_none
- Use repeat() loops for master sequences with correct transaction counts
- **CRITICAL:** Insert package includes BEFORE `endpackage` using sed:

```bash
# WRONG - appends after endpackage!
echo '`include "file.sv"' >> "$PKG_FILE"

# CORRECT - inserts before endpackage
sed -i '/^endpackage/i \  `include "student_example_incr_burst_write_seq.sv"' "$MASTER_PKG"
sed -i '/^endpackage/i \  `include "student_example_incr_burst_read_seq.sv"' "$MASTER_PKG"
sed -i '/^endpackage/i \  `include "student_example_incr_burst_virtual_seq.sv"' "$VIRTUAL_PKG"
sed -i '/^endpackage/i \  `include "student_example_incr_burst_write_read_test.sv"' "$TEST_PKG"
```

**Two approaches depending on whether you need custom sequences:**

**Approach A:** Task uses existing production sequences (like 32b task)
- Don't delete production sequences in clean_repo.sh
- Virtual sequence references existing sequences (e.g., `axi4_master_bk_write_32b_transfer_seq`)
- No need to create custom master sequences
- No need to add includes to master_seq_pkg

**Approach B:** Task requires custom sequences (like INCR task)
- Delete production sequences that give away solution in clean_repo.sh
- Create custom master/slave sequences in solution.sh
- Add includes to packages BEFORE endpackage

**Key points:**
- Use heredocs (`cat > file << 'EOF'`) to create multi-line files
- Single quotes in `<< 'EOF'` prevent variable expansion
- Recreate EXACTLY the files that clean_repo.sh removes
- No typos! (e.g., "Instantiation" not "Instatiation", "Inside" not "Insdie")

See axi4_blocking_incr_burst_write_read_test/solution.sh for Approach B example.
See axi4_blocking_32b_write_read_test/solution.sh for Approach A example.

**Don't forget:**
```bash
chmod +x axi4_blocking_incr_burst_write_read_test/solution.sh
```

### Step 2.6: Create clean_repo.sh

Create `axi4_blocking_incr_burst_write_read_test/resources/clean_repo.sh`:

This script removes production test files and solution files to create an exam environment.

**CRITICAL DECISIONS:**

**Decision 1: Which production files to delete?**
- Always delete: The test file itself (e.g., `axi4_blocking_incr_burst_write_read_test.sv`)
- Always delete: Related virtual sequence files
- **IMPORTANT DECISION:** Should you delete production master/slave sequences?

  **Delete them if:** They contain the exact solution constraints students need to figure out
  ```bash
  # Example: INCR task - these files show the exact awsize and awburst values
  rm -f "$MASTER_SEQ_DIR/axi4_master_bk_write_incr_burst_seq.sv"
  rm -f "$MASTER_SEQ_DIR/axi4_master_bk_read_incr_burst_seq.sv"
  ```

  **Keep them if:** They're generic enough that students can use them
  ```bash
  # Example: 32b task - these are generic size-specific sequences
  # Don't delete axi4_master_bk_write_32b_transfer_seq.sv - students can use it
  ```

**CRITICAL POINT:** The sed patterns must match the exact format of include statements in the package files. In SystemVerilog, includes use backticks:

```systemverilog
`include "filename.sv"
```

So the sed pattern must be:
```bash
sed -i '/`include "filename\.sv"/d' "$PKG_FILE"
```

NOT:
```bash
sed -i '/filename\.sv/d' "$PKG_FILE"  # WRONG - won't match
```

**Complete example for INCR task (Approach B - custom sequences needed):**
```bash
#!/bin/bash
# Remove production tests that overlap with exam tasks
# This prevents students from copy-pasting solutions

set -e

# Ensure that TB_HOME is set
if [ -z "$TB_HOME" ]; then
    echo "Error: TB_HOME environment variable is not set."
    exit 1
fi

TEST_DIR="$TB_HOME/src/hvl_top/test"
PKG_FILE="$TEST_DIR/axi4_test_pkg.sv"
VIRTUAL_SEQ_DIR="$TEST_DIR/virtual_sequences"
MASTER_SEQ_DIR="$TEST_DIR/sequences/master_sequences"

echo "Removing overlapping production tests and example solutions..."

# Remove production test files for incr burst tests
rm -f "$TEST_DIR/axi4_blocking_incr_burst_write_read_test.sv"
rm -f "$TEST_DIR/axi4_non_blocking_incr_burst_write_read_test.sv"

# Remove virtual sequences that reference deleted master sequences
rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_bk_incr_burst_write_read_seq.sv"
rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_nbk_incr_burst_write_read_seq.sv"

# Remove production master sequence files that give away solution
rm -f "$MASTER_SEQ_DIR/axi4_master_bk_write_incr_burst_seq.sv"
rm -f "$MASTER_SEQ_DIR/axi4_master_bk_read_incr_burst_seq.sv"

# Remove from package file - CRITICAL: Use backtick format
sed -i '/`include "axi4_blocking_incr_burst_write_read_test\.sv"/d' "$PKG_FILE"
sed -i '/`include "axi4_non_blocking_incr_burst_write_read_test\.sv"/d' "$PKG_FILE"

# Remove from virtual sequence package
VIRTUAL_PKG="$VIRTUAL_SEQ_DIR/axi4_virtual_seq_pkg.sv"
if [ -f "$VIRTUAL_PKG" ]; then
    sed -i '/`include "axi4_virtual_bk_incr_burst_write_read_seq\.sv"/d' "$VIRTUAL_PKG"
    sed -i '/`include "axi4_virtual_nbk_incr_burst_write_read_seq\.sv"/d' "$VIRTUAL_PKG"
fi

# Remove from master sequence package
MASTER_PKG="$MASTER_SEQ_DIR/axi4_master_seq_pkg.sv"
if [ -f "$MASTER_PKG" ]; then
    sed -i '/`include "axi4_master_bk_write_incr_burst_seq\.sv"/d' "$MASTER_PKG"
    sed -i '/`include "axi4_master_bk_read_incr_burst_seq\.sv"/d' "$MASTER_PKG"
fi

echo "✓ Removed: axi4_blocking_incr_burst_write_read_test.sv and related files"
echo "✓ Updated: package files"

# Copy AGENTS.md to repo root
cp /resources/AGENTS.md "$TB_HOME/AGENTS.md"
echo "✓ Copied: AGENTS.md"
```

**Common issue:** If you get compilation errors like "cannot open include file", check that your sed patterns match the actual format in the package files by running:
```bash
grep -n "filename" ~/axi4_avip/src/hvl_top/test/axi4_test_pkg.sv
```

See axi4_blocking_incr_burst_write_read_test/resources/clean_repo.sh for Approach B example.
See axi4_blocking_32b_write_read_test/resources/clean_repo.sh for Approach A example.

### Step 2.7: Create coverage_requirements.txt

Create `axi4_blocking_wrap_burst_write_read_test/resources/coverage_requirements.txt`:

**CRITICAL: Match actual test behavior!**

Based on Step 1.4-1.5 analysis, write coverage requirements that match what the test's sequence constraints actually guarantee.

**Format:**
```
# Comment describing requirement
coverpoint|bin_name|minimum_coverage_percentage
```

**How to get exact bin names:**
```bash
cd ~/axi4_avip/sim/cadence_sim
imc -load axi4_blocking_wrap_burst_write_read_test -execcmd "report -detail -covered"
```

Look for lines like:
```
AWBURST_CP
  READ_WRAP                  100.00%  (covered)
```

The bin name is `READ_WRAP`, not `WRITE_WRAP` or `AWBURST_WRAP`.

**CORRECT approach (match actual test behavior):**
```
# Coverage Requirements for INCR Burst Read Test
# Format: coverpoint|bin|minimum_coverage_percentage
#
# These requirements are based on ACTUAL test behavior
# This test performs only read transactions with INCR burst type and 4-byte transfers

# Read Address Channel - Transfer Size
# Test uses 4-byte (32-bit) transfers only
ARSIZE_CP|ARSIZE_4BYTES|100

# Read Address Channel - Burst Type
# Primary focus: INCR burst type
ARBURST_CP|WRITE_INCR|100
```

**WRONG approach (don't do this):**
```
# ❌ WRONG - Test doesn't constrain burst length!
ARLEN_CP|ARLEN_1|100
ARLEN_CP|ARLEN_2|100
ARLEN_CP|ARLEN_4|100

# ❌ WRONG - Test only uses 4-byte transfers!
ARSIZE_CP|ARSIZE_1BYTE|100
ARSIZE_CP|ARSIZE_2BYTES|100
```

**Key principle:** Only require coverage bins that the test's sequence constraints guarantee to hit. Check the sequence code to see which parameters are FIXED vs RANDOM.

### Step 2.8: Create AGENTS.md

Create `axi4_blocking_wrap_burst_write_read_test/resources/AGENTS.md`:

This file provides context to AI agents about the testbench environment. Include:
- Directory structure
- How to compile and simulate
- How to check coverage
- Naming conventions
- Code examples
- Common patterns

**Note:** The AGENTS.md file is generic and can be copied from existing tasks:
```bash
cp axi4_blocking_32b_write_read_test/resources/AGENTS.md axi4_blocking_wrap_burst_write_read_test/resources/
```

### Step 2.9: Create Test Files

**Copy test infrastructure:**
```bash
cp -r axi4_blocking_32b_write_read_test/tests/* axi4_blocking_wrap_burst_write_read_test/tests/
```

**Note:** The test infrastructure (test_outputs.py, standard_grader.py) is generic and works for all tasks.

**Create run-tests.sh:**

Create `axi4_blocking_wrap_burst_write_read_test/run-tests.sh`:

```bash
#!/bin/bash
# Terminal Bench test runner script
# This script is executed by Terminal Bench to run the tests

set -e

cd /tests

# Run pytest with the test file
# -rA: show extra test summary info for ALL outcomes including passes
# This is required for Terminal Bench's pytest parser to work
pytest test_outputs.py -v -s -rA
```

**CRITICAL: Use `-rA` flag (uppercase A)**

**Why not other flags?**
- `-ra` (lowercase): Shows "all except passes" - when all tests pass, no "short test summary info" section is generated, causing parser to fail
- `-rP`: Shows only passed tests, not the summary section parser needs
- `-rA` (uppercase): Shows ALL outcomes including passes - ALWAYS generates summary section

**Terminal Bench's pytest parser requires the "short test summary info" section to be present.**

**Don't forget:**
```bash
chmod +x axi4_blocking_wrap_burst_write_read_test/run-tests.sh
```

---

## Phase 3: Validation Phase

### Step 3.1: Initial Test Run

Run the oracle agent to test your task:

```bash
cd /home/thomas-ahle/dv-smith/thomas_tasks
tb run -a oracle -t axi4_blocking_wrap_burst_write_read_test --dataset-path .
```

**Expected result:**
```
Resolved Trials: 1
Unresolved Trials: 0
Accuracy: 100.00%
```

### Step 3.2: Analyze Failures

If the test fails (accuracy < 100%), examine the results:

```bash
# Find the latest run
ls -lt runs/

# Check results
cat runs/2025-11-11__XX-XX-XX/results.json

# Check test output
tail -100 runs/2025-11-11__XX-XX-XX/axi4_blocking_wrap_burst_write_read_test/axi4_blocking_wrap_burst_write_read_test.1-of-1.*/panes/post-test.txt
```

### Step 3.3: Common Issues and Fixes

#### Issue 1: Docker Build Failures

**Symptom:** Docker build fails with package dependency errors

**Diagnosis:**
```bash
docker compose -f axi4_blocking_wrap_burst_write_read_test/docker-compose.yaml build
```

**Common fixes:**
- Pin Python package versions (pytest==8.0.0, vcdvcd==2.6.0)
- Use compatible package versions
- Check for deprecated or unavailable packages

#### Issue 2: Compilation Failures

**Symptom:** `xmvlog: *E,COFILX: cannot open include file`

**Diagnosis:**
```bash
grep "include" ~/axi4_avip/src/hvl_top/test/axi4_test_pkg.sv
```

**Fix:** Update sed patterns in clean_repo.sh to match exact format with backticks

#### Issue 3: Coverage Failures

**Symptom:** Coverage requirements not met

**Diagnosis:**
```bash
cd ~/axi4_avip/sim/cadence_sim
imc -load student_example_wrap_burst_write_read_test -execcmd "report -detail -covered"
```

**Fix:** Update coverage_requirements.txt with exact bin names from coverage report

#### Issue 4: Simulation Failures

**Symptom:** UVM_ERROR or UVM_FATAL messages

**Diagnosis:**
```bash
cat ~/axi4_avip/sim/cadence_sim/xrun_student_example_wrap_burst_write_read_test.log
```

**Common fixes:**
- Check transaction constraints match expected values
- Verify slave sequences are started correctly
- Check objection handling in test

#### Issue 5: Test name mismatch
**Symptom:** `UVM_FATAL: Requested test from command line +UVM_TESTNAME=X not found`

**Fix:** Ensure TEST_NAME is consistent in:
- Dockerfile
- docker-compose.yaml
- task.yaml instruction
- solution.sh (class name)

#### Issue 6: pytest parser fails
**Symptom:** `No short test summary info found`

**Fix:** Change pytest flag from `-ra` or `-rP` to `-rA` in run-tests.sh

#### Issue 7: Agent can't install
**Symptom:** `404 Client Error for .../installed-agent: Not Found`

**Fix:** Remove `user: "1000:1000"` from docker-compose.yaml

### Step 3.4: Iterate Until Success

Repeat the test-diagnose-fix cycle:

```bash
# Fix the issue
# (edit relevant files)

# Test again
tb run -a oracle -t axi4_blocking_wrap_burst_write_read_test --dataset-path .

# Repeat until accuracy = 100%
```

### Step 3.5: Final Validation

Once you achieve 100% accuracy:

```bash
# Run one final time to confirm
tb run -a oracle -t axi4_blocking_wrap_burst_write_read_test --dataset-path .

# Verify task validation
tb tasks check axi4_blocking_wrap_burst_write_read_test --tasks-dir .
```

**Expected warnings:**
- "Test dependencies in image" - by design for this testbench
- "Anti-cheating measures" - coverage_requirements.txt in image is acceptable
- Other warnings are informational

---

## Summary Checklist

- [ ] Selected appropriate test file from testbench
- [ ] Analyzed test structure, virtual sequence, and master sequences
- [ ] Ran simulation and extracted exact coverage bin names
- [ ] Created task directory structure
- [ ] Created Dockerfile with pinned dependencies and correct PATH
- [ ] Created docker-compose.yaml without user specification
- [ ] Created task.yaml with clear, consistent instructions
- [ ] Created solution.sh that generates complete working solution with correct sed patterns
- [ ] Created clean_repo.sh that removes entire dependency chain
- [ ] Created coverage_requirements.txt matching actual test behavior
- [ ] Created AGENTS.md with environment documentation
- [ ] Created run-tests.sh with `-rA` flag
- [ ] Copied pytest test infrastructure
- [ ] All scripts are executable (chmod +x)
- [ ] Tested with oracle agent
- [ ] Fixed all issues until 100% accuracy achieved
- [ ] Verified task validation passes

---

## Key Lessons Learned

### Critical Infrastructure Issues (Discovered during axi4_blocking_incr_burst_write_read_test)

1. **Docker Strategy - Repository Cloning vs Mounting**
   - **WRONG:** Mounting the repository as a volume in docker-compose.yaml
   - **CORRECT:** Clone the repository during Dockerfile build with `git clone`
   - **Rationale:** The repository needs to be modified by clean_repo.sh during image build, and changes must be baked into the image
   - **Implementation:**
     ```dockerfile
     # In Dockerfile
     RUN git clone --depth=1 https://github.com/mbits-mirafra/axi4_avip.git /axi4_avip
     ```
   - **Remove from docker-compose.yaml:** Don't mount the repo as a volume

2. **Docker Strategy - Resource Files**
   - **WRONG:** Mounting resources directory as a volume
   - **CORRECT:** COPY resources into the Docker image during build
   - **Implementation:**
     ```dockerfile
     # In Dockerfile
     COPY resources/clean_repo.sh /tmp/clean_repo.sh
     COPY resources/coverage_requirements.txt /resources/coverage_requirements.txt
     COPY resources/AGENTS.md /resources/AGENTS.md

     RUN bash /tmp/clean_repo.sh && rm /tmp/clean_repo.sh
     ```

3. **Cadence Tools PATH Configuration**
   - **WRONG:** Setting PATH in docker-compose environment or run-tests.sh
   - **CORRECT:** Set PATH in Dockerfile ENV
   - **Implementation:**
     ```dockerfile
     ENV PATH="/opt/cadence/installs/XCELIUM2403/tools/bin/64bit:\
     /opt/cadence/installs/VMANAGER2403/bin:\
     ${PATH}"
     ```
   - **Note:** Use the correct Xcelium version (XCELIUM2403, not xcelium2309)

4. **Deleting Production Sequences That Give Away Solutions**
   - **Issue:** When creating a task based on production tests, must delete BOTH:
     - The test file itself
     - The virtual sequence file
     - **AND** the master/slave sequence files that contain the exact solution
   - **Example for INCR burst task:**
     ```bash
     # In clean_repo.sh
     # Delete production master sequences that show exact constraints
     rm -f "$MASTER_SEQ_DIR/axi4_master_bk_write_incr_burst_seq.sv"
     rm -f "$MASTER_SEQ_DIR/axi4_master_bk_read_incr_burst_seq.sv"

     # Also remove from package files
     sed -i '/`include "axi4_master_bk_write_incr_burst_seq\.sv"/d' "$MASTER_PKG"
     sed -i '/`include "axi4_master_bk_read_incr_burst_seq\.sv"/d' "$MASTER_PKG"
     ```
   - **Contrast with 32b task:** The 32b task uses existing production sequences, so doesn't need custom sequences

5. **Package Include Placement**
   - **Issue:** When solution.sh creates custom sequences, the include statements must go BEFORE the `endpackage` statement
   - **WRONG:** Appending to end of package file with `>>`
     ```bash
     echo '`include "file.sv"' >> "$PKG_FILE"  # WRONG - goes after endpackage!
     ```
   - **CORRECT:** Insert before endpackage using sed
     ```bash
     sed -i '/^endpackage/i \  `include "student_example_incr_burst_write_seq.sv"' "$MASTER_PKG"
     ```
   - **Why:** Includes outside the package declaration won't be visible to code inside the package

6. **Dockerfile Multi-layer Optimization**
   - Combine related RUN commands to minimize layers
   - Install all system packages in one RUN command
   - Clean up package caches in the same layer: `&& dnf clean all && rm -rf /var/cache/dnf`

7. **Virtual Sequences Referencing Deleted Master Sequences**
   - **Issue:** When you delete production master sequences (issue #4 above), you must ALSO delete any virtual sequences that reference them
   - **Symptom:** Compilation errors like "Unrecognized declaration 'axi4_master_bk_write_incr_burst_seq'"
   - **Root Cause:** Virtual sequences instantiate and use the master sequences. If the master sequences are deleted but the virtual sequences remain, compilation will fail.
   - **Solution:** Delete the corresponding virtual sequences AND remove their includes from the virtual sequence package
   - **Example for INCR burst task:**
     ```bash
     # In clean_repo.sh
     # Delete virtual sequences that reference the deleted master sequences
     rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_bk_incr_burst_write_seq.sv"
     rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_bk_incr_burst_read_seq.sv"
     rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_nbk_incr_burst_write_seq.sv"
     rm -f "$VIRTUAL_SEQ_DIR/axi4_virtual_nbk_incr_burst_read_seq.sv"

     # Also remove from virtual sequence package
     sed -i '/`include "axi4_virtual_bk_incr_burst_write_seq\.sv"/d' "$VIRTUAL_PKG"
     sed -i '/`include "axi4_virtual_bk_incr_burst_read_seq\.sv"/d' "$VIRTUAL_PKG"
     sed -i '/`include "axi4_virtual_nbk_incr_burst_write_seq\.sv"/d' "$VIRTUAL_PKG"
     sed -i '/`include "axi4_virtual_nbk_incr_burst_read_seq\.sv"/d' "$VIRTUAL_PKG"
     ```
   - **When to apply:** Any time you delete master sequences that show the solution

8. **Tests Referencing Deleted Virtual Sequences**
   - **Issue:** When you delete virtual sequences, you must also delete any test files that reference them
   - **Symptom:** Compilation errors like "Unrecognized declaration 'axi4_virtual_nbk_incr_burst_write_seq'"
   - **Root Cause:** Tests instantiate virtual sequences. If virtual sequences are deleted but tests remain, compilation fails.
   - **Solution:** Delete test files that reference deleted virtual sequences
   - **Example:**
     ```bash
     # In clean_repo.sh
     # Delete tests that reference deleted virtual sequences
     rm -f "$TEST_DIR/axi4_non_blocking_incr_burst_write_test.sv"
     rm -f "$TEST_DIR/axi4_non_blocking_incr_burst_read_test.sv"
     ```
   - **When to apply:** When deleting virtual sequences, check for tests that use them

### Additional Lessons

9. **pytest flag MUST be -rA**
   - When all tests pass, pytest with `-ra` (all except passes) doesn't generate the "short test summary info" section
   - Terminal Bench's parser requires this section, so we must use `-rA` (all including passes)

10. **Container MUST run as root**
   - The `user: "1000:1000"` setting prevents the claude-code agent from installing
   - Agent needs root to create `/installed-agent` directory and run `apt-get`

11. **Coverage requirements MUST match actual behavior**
   - Don't write wishful requirements! Analyze the sequence constraints:
   - If sequence constrains `arsize == READ_4_BYTES`, only require ARSIZE_4BYTES
   - If burst length is NOT constrained, don't require specific ARLEN bins
   - Test actual simulation to confirm what bins are hit

12. **Test naming MUST be consistent**
   - The TEST_NAME environment variable must match:
     - UVM test class name in code
     - task.yaml instruction
     - Dockerfile ENV
     - docker-compose.yaml environment
     - solution.sh generated class name

13. **Always use exact bin names from coverage database**
   - Don't assume bin naming conventions
   - Use imc to extract exact bin names from coverage report

14. **Match sed patterns exactly to file format**
   - SystemVerilog uses backticks for includes: `` `include "file.sv" ``
   - Sed pattern must match: `sed -i '/`include "file\.sv"/d' "$PKG"`

15. **Coverage database location**
   - After `make simulate test=<name>`, database is at: `cov_work/scope/<test_name>`
   - NOT at `cov_work/scope/<test_name>/<test_name>`

---

## Example Commands Reference

```bash
# Analysis Phase
ls ~/axi4_avip/src/hvl_top/test/
cat ~/axi4_avip/src/hvl_top/test/<test_name>.sv
find ~/axi4_avip -name "*<pattern>*seq.sv"
cd ~/axi4_avip/sim/cadence_sim
make compile
make simulate test=<test_name>
imc -load <test_name> -execcmd "report -summary"
imc -load <test_name> -execcmd "report -detail -covered"

# Creation Phase
mkdir -p <task_name>/{resources,tests}
chmod +x <task_name>/*.sh
chmod +x <task_name>/resources/*.sh

# Validation Phase
tb run -a oracle -t <task_name> --dataset-path .
cat runs/<latest>/results.json
tb tasks check <task_name> --tasks-dir .

# Debugging
docker compose -f <task_name>/docker-compose.yaml build
grep "include" ~/axi4_avip/src/hvl_top/test/axi4_test_pkg.sv
cat ~/axi4_avip/sim/cadence_sim/xrun_<test_name>.log
cat runs/$(ls -t runs/ | head -1)/*/panes/post-test.txt
```

---

## Summary

Successfully creating a terminal bench task requires:

1. ✅ **Thorough analysis** of the reference test and its sequences
2. ✅ **Running actual simulation** to see what coverage is achieved
3. ✅ **Matching coverage requirements** to actual test behavior (not wishful thinking!)
4. ✅ **Consistent naming** across all files (Dockerfile, docker-compose, task.yaml, solution)
5. ✅ **Correct Docker strategy** - clone repo and copy resources during build
6. ✅ **Proper PATH configuration** - set in Dockerfile ENV
7. ✅ **Complete dependency chain deletion** - master sequences → virtual sequences → tests
8. ✅ **Correct sed patterns** - insert before endpackage, match backtick format
9. ✅ **Using `-rA` flag** in run-tests.sh for pytest
10. ✅ **Running as root** (no user specification in docker-compose)
11. ✅ **Testing with oracle** agent until 100% accuracy achieved
12. ✅ **Iterative debugging** - fix one issue at a time

**The most critical insights:**
- Coverage requirements must match what the test's sequence constraints actually guarantee
- When deleting master sequences, also delete virtual sequences that reference them
- When deleting virtual sequences, also delete tests that reference them
- Repository and resources must be in the Docker image, not mounted as volumes
- Package includes must be inserted before endpackage, not appended after

---

**Last updated:** 2025-11-12 after merging TASK_CREATION_GUIDE.md and TASK_CREATION_PROCEDURE.md
