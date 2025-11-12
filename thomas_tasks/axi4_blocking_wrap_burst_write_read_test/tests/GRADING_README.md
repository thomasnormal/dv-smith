# Enhanced Automated Test Grading System

## Overview

Comprehensive grading system that validates **three critical aspects** of student tests:

1. **Scoreboard Validation (40%)** - Does the test pass functional checks?
2. **Functional Coverage (50%)** - Does the test hit required coverage bins?
3. **Performance Metrics (10%)** - How efficient is the test?

## Why These Three Metrics?

### 1. Scoreboard Validation (40% weight)

**Why it matters:** Coverage metrics are meaningless if the test has functional errors.

A student could write a test that hits all coverage bins but generates incorrect transactions. The scoreboard detects:
- Protocol violations
- Data mismatches
- Unexpected behavior

**What we check:**
- ✅ Zero UVM_ERROR messages
- ✅ Zero UVM_FATAL messages
- ✅ Zero data mismatches (if scoreboard reports them)

**Example failure:**
```
Student test achieves 100% coverage but:
- Writes wrong data values
- Uses illegal burst types
- Violates AXI4 protocol rules
→ Scoreboard: FAIL (0%) → Final Grade: 50%
```

### 2. Functional Coverage (50% weight)

**Why it matters:** Ensures test generates required stimulus.

**What we check:**
- Did test hit specific coverage bins? (e.g., AWLEN_8, ARSIZE_4BYTES)
- Verified via IMC coverage analysis
- Same as previous grading system

### 3. Performance Metrics (10% weight)

**Why it matters:** Tests should be efficient - don't waste simulation time.

**What we check:**
- Simulation time (ns)
- Coverage efficiency (coverage% per μs)

**Efficiency scoring:**
- Excellent (100%): > 10 coverage%/μs
- Good (80%): > 5 coverage%/μs
- Acceptable (60%): > 2 coverage%/μs
- Poor (40%): ≤ 2 coverage%/μs

**Example:**
```
Test A: 100% coverage in 10,000 ns → 10 cov%/μs → Performance: 100%
Test B: 100% coverage in 100,000 ns → 1 cov%/μs → Performance: 40%
Both get 100% coverage, but Test A is 10x more efficient!
```

## Usage

### Standalone Python

```bash
python3 test_grade_enhanced.py <test_name> <requirements_file>

# Example:
python3 test_grade_enhanced.py axi4_blocking_32b_write_read_test exam_32b_write_read_requirements.txt
```

### Pytest

```bash
pytest test_grade_enhanced.py --test-name=<test> --requirements=<req_file> -v -s

# Example:
pytest test_grade_enhanced.py --test-name=axi4_blocking_32b_write_read_test \
                               --requirements=exam_32b_write_read_requirements.txt -v -s
```

## Output Example

```
================================================================================
COMPREHENSIVE GRADING REPORT
================================================================================

--- SCOREBOARD VALIDATION ---
✓ PASS: Scoreboard check
       UVM Errors:   0
       UVM Warnings: 0
       UVM Fatals:   0
       Data Mismatches: 0
       Total Transactions: 0

--- FUNCTIONAL COVERAGE ---
✓ PASS: AWLEN_CP -> AWLEN_1
       Coverage: 100.00% (required: 100%)
✓ PASS: AWLEN_CP -> AWLEN_4
       Coverage: 100.00% (required: 100%)
...

--- PERFORMANCE METRICS ---
Simulation Time:     4,110 ns
Wall Clock Time:     0.00 sec
Total Transactions:  0
Transaction Rate:    0.00 trans/μs
Efficiency:          24.331 coverage%/μs

================================================================================
FINAL GRADE
================================================================================
Scoreboard:  100.0% (weight: 40%)
Coverage:    100.0% (weight: 50%)
Performance: 100.0% (weight: 10%)

FINAL GRADE: 100.00%
================================================================================
```

## Grading Formula

```
Final Grade = (Scoreboard × 0.4) + (Coverage × 0.5) + (Performance × 0.1)

Where:
  Scoreboard  = 100 if no errors/fatals, else 0
  Coverage    = % of requirements met
  Performance = Efficiency-based score (40-100)
```

## Interpreting Results

### Scenario 1: Perfect Test
```
Scoreboard:  100% ✓
Coverage:    100% ✓
Performance: 100% ✓
→ FINAL GRADE: 100%
```

### Scenario 2: Functional Errors
```
Scoreboard:  0%  ✗ (3 UVM_ERRORs detected)
Coverage:    100% ✓
Performance: 80%  ✓
→ FINAL GRADE: 58%
⚠️  Coverage is meaningless with scoreboard failures!
```

### Scenario 3: Incomplete Coverage
```
Scoreboard:  100% ✓
Coverage:    60%  ⚠️ (3/5 requirements met)
Performance: 100% ✓
→ FINAL GRADE: 70%
```

### Scenario 4: Inefficient Test
```
Scoreboard:  100% ✓
Coverage:    100% ✓
Performance: 40%  ⚠️ (very slow, 1 cov%/μs)
→ FINAL GRADE: 94%
```

## Customizing Weights

Edit the grader to adjust importance:

```python
# In test_grade_enhanced.py, line ~340

# Default weights
scoreboard_weight = 0.4   # 40%
coverage_weight = 0.5     # 50%
performance_weight = 0.1  # 10%

# Example: Make coverage more important
scoreboard_weight = 0.3   # 30%
coverage_weight = 0.6     # 60%
performance_weight = 0.1  # 10%

# Example: Ignore performance
scoreboard_weight = 0.45  # 45%
coverage_weight = 0.55    # 55%
performance_weight = 0.0  # 0%
```

## Performance Thresholds

Adjust efficiency thresholds:

```python
# In test_grade_enhanced.py, line ~350

# Current thresholds
if eff > 10:
    performance_score = 100  # Excellent
elif eff > 5:
    performance_score = 80   # Good
elif eff > 2:
    performance_score = 60   # Acceptable
else:
    performance_score = 40   # Poor

# Example: More strict
if eff > 20:
    performance_score = 100  # Excellent
elif eff > 10:
    performance_score = 80   # Good
elif eff > 5:
    performance_score = 60   # Acceptable
else:
    performance_score = 40   # Poor
```

## What Gets Checked

### Scoreboard Validation (from log file)

**Checks for:**
```bash
# Actual error messages (not summaries)
UVM_ERROR @
UVM_FATAL @
UVM_WARNING @

# Optional: Scoreboard messages
"Data mismatch"
"Data matched"
```

**Ignores:**
```bash
# Summary lines (don't count as errors)
UVM_ERROR : 0
Number of caught UVM_ERROR reports : 0
```

### Performance Metrics (from log file)

**Simulation time extraction:**
```
"Simulation complete via $finish(1) at time 4110 NS"
→ Extracted: 4110 ns
```

**Transaction counting (optional):**
```
"Write transaction completed"
"Read transaction completed"
→ Counts total transactions if messages present
```

## Comparison: Basic vs Enhanced

| Feature | Basic Grader | Enhanced Grader |
|---------|--------------|-----------------|
| **Coverage checking** | ✅ | ✅ |
| **Scoreboard validation** | ❌ | ✅ |
| **Performance metrics** | ❌ | ✅ |
| **Weighted grading** | ❌ | ✅ |
| **Simulation time** | ❌ | ✅ |
| **Error detection** | ❌ | ✅ |
| **Exit code on failure** | Coverage only | Scoreboard OR coverage |

## Practical Use Cases

### Use Case 1: Catch Incorrect Tests

**Student test:**
```systemverilog
// Student writes random values without checking alignment
constraint bad_constraint {
  awaddr == $urandom;  // Not aligned!
  awsize == 3;         // 8-byte transfers
}
```

**Result:**
```
Scoreboard: FAIL ✗ (protocol violation errors)
Coverage:   100% ✓ (hit all bins)
→ FINAL GRADE: 50%
```

### Use Case 2: Encourage Efficiency

**Student A:** Achieves coverage in 5,000 ns
**Student B:** Achieves coverage in 50,000 ns

Both get 100% coverage, but:
- Student A: Performance 100% → Grade 100%
- Student B: Performance 40% → Grade 96%

Teaches students to write efficient tests!

### Use Case 3: Progressive Grading

For partial credit scenarios:

**Test hits 8/12 coverage requirements:**
```
Scoreboard:  100%
Coverage:    67% (8/12 requirements)
Performance: 80%
→ FINAL GRADE: 81.5%
```

Student gets most of the credit even if coverage incomplete.

## Integration with CI/CD

```python
# batch_grade.py
import subprocess
import json

students = ['alice', 'bob', 'charlie']
results = {}

for student in students:
    result = subprocess.run(
        ['python3', 'test_grade_enhanced.py',
         f'{student}_test', 'exam_requirements.txt'],
        capture_output=True,
        text=True
    )

    # Parse output for grade
    for line in result.stdout.split('\n'):
        if 'FINAL GRADE:' in line:
            grade = float(line.split(':')[1].strip().replace('%', ''))
            results[student] = {
                'grade': grade,
                'passed': result.returncode == 0
            }

# Generate report
with open('grades.json', 'w') as f:
    json.dump(results, f, indent=2)
```

## Troubleshooting

### False scoreboard failures

If grader reports errors but log shows "UVM_ERROR : 0":
- Check regex patterns in `LogAnalyzer.analyze_scoreboard()`
- Pattern looks for `UVM_ERROR @` (actual errors)
- Summary lines like `UVM_ERROR : 0` are ignored

### Simulation time = 0

If performance shows 0 ns:
- Check log file for finish message
- Update regex in `LogAnalyzer.analyze_performance()`
- Look for: `"at time (\d+) NS"`

### Transaction count = 0

Not all testbenches print transaction messages - this is OK!
- Transaction counting is optional
- Only affects detailed reporting, not grading
- Scoreboard pass/fail is based on errors, not transaction count

## Files

- `test_grade_enhanced.py` - Enhanced grading script (450+ lines)
- `conftest.py` - Pytest configuration
- `exam_32b_write_read_requirements.txt` - Example requirements
- `ENHANCED_GRADING_README.md` - This file

## Summary

The enhanced grader ensures students write **correct, complete, and efficient** tests:

1. ✅ **Scoreboard (40%)** - Test is functionally correct
2. ✅ **Coverage (50%)** - Test hits required scenarios
3. ✅ **Performance (10%)** - Test is efficient

This mirrors real verification work where all three matter!
