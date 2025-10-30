# Understanding Evaluation in DV-Smith

> **Note**
> The standalone `dvsmith eval` command has been retired. Evaluation now runs
> through Terminal Bench workflows (`tb run` and related helpers). The scoring
> model and artifacts described below still apply; only the invocation method
> has changed.

This tutorial explains how DV-Smith evaluates agent solutions and calculates scores.

## Evaluation Overview

DV-Smith evaluates solutions based on three key metrics:
1. **Functional Coverage** (typically 60% weight)
2. **Code Coverage** (typically 30% weight)
3. **Health Metrics** (typically 10% weight)

## Evaluation Process

### 1. Apply Solution

```bash
tb run --dataset-path <tasks_dir> --task-id <task-id>
```

**Steps:**
1. Create clean copy of gym repository
2. Apply the patch file
3. Verify patch applies cleanly
4. Check for compilation errors

### 2. Compile Design

**Process:**
- Run compilation command from profile
- Check for syntax errors
- Verify all files compile successfully

**Failures:**
- Missing files → Score: 0
- Syntax errors → Score: 0
- Link errors → Score: 0

### 3. Run Simulation

**Process:**
- Execute test with coverage enabled
- Capture simulation log
- Monitor for timeouts (default: 300s)

**Coverage Flags:**
- **Xcelium**: `-coverage all -covdut top`
- **Questa**: `-coverage -coverstore <db>`
- **VCS**: `-cm line+cond+fsm+tgl+branch`

### 4. Extract Coverage

**Functional Coverage:**
- Parse covergroups and bins
- Check hit counts vs goals
- Calculate overall percentage

**Code Coverage:**
- Statement coverage
- Branch coverage
- Toggle coverage
- FSM coverage (if present)

**Coverage Database Locations:**
- Xcelium: `cov_work/` (IMC database with `functional.txt` and `code.txt` reports)
- Questa: `*.ucdb` (UCDB database)
- VCS: `simv.vdb/` (VDB database)

**Xcelium Coverage Parsing:**
- Primary: Parses `code.txt` and `functional.txt` from IMC reports
- Fallback: If `code.txt` is missing, parses `summary.txt` for code coverage metrics
- This ensures coverage data is extracted even when detailed reports aren't available

### 5. Parse Health Metrics

**From simulation log:**
- UVM_ERROR count
- UVM_FATAL count
- UVM_WARNING count (informational)
- Scoreboard mismatches
- Assertion failures
- Timeout status

### 6. Calculate Score

```python
total_score = (
    functional_score * weight_functional +
    code_score * weight_code +
    health_score * weight_health
)
```

## Scoring Details

### Functional Coverage Scoring

**Strategy: any_of** (most common)
```python
def score_functional_any_of(coverage_report, acceptance):
    """Score if ANY target bin is hit."""
    bins_met = []
    bins_missed = []

    for target_bin in acceptance.functional_bins:
        # Parse bin path: "covergroup.coverpoint.bin"
        cg_name, bin_name = parse_bin_path(target_bin)

        # Find in coverage report
        cg = find_covergroup(coverage_report, cg_name)
        if cg and cg.get_bin(bin_name):
            bin = cg.get_bin(bin_name)
            if bin.is_covered:  # hits >= goal
                bins_met.append(target_bin)
            else:
                bins_missed.append(target_bin)

    # Score based on percentage of bins met
    if len(acceptance.functional_bins) > 0:
        score = 100.0 * len(bins_met) / len(acceptance.functional_bins)
    else:
        # No specific bins, use overall percentage
        score = calculate_overall_functional_coverage(coverage_report)

    return score
```

**Strategy: all_of** (stricter)
```python
def score_functional_all_of(coverage_report, acceptance):
    """Score only if ALL target bins are hit."""
    all_met = all(
        is_bin_covered(coverage_report, bin)
        for bin in acceptance.functional_bins
    )

    if all_met:
        return 100.0
    else:
        # Partial credit
        bins_met = sum(1 for bin in acceptance.functional_bins
                      if is_bin_covered(coverage_report, bin))
        return 100.0 * bins_met / len(acceptance.functional_bins)
```

### Code Coverage Scoring

```python
def score_code_coverage(coverage_report, acceptance):
    """Score based on statement, branch, and toggle coverage."""
    statement_score = min(100.0,
        100.0 * coverage_report.code_coverage.statements_pct /
        acceptance.code_statements_min_pct
    )

    branch_score = min(100.0,
        100.0 * coverage_report.code_coverage.branches_pct /
        acceptance.code_branches_min_pct
    )

    toggle_score = min(100.0,
        100.0 * coverage_report.code_coverage.toggles_pct /
        acceptance.code_toggles_min_pct
    )

    # Average of all code metrics
    code_score = (statement_score + branch_score + toggle_score) / 3.0

    return code_score
```

### Health Scoring

```python
def score_health(coverage_report, acceptance):
    """Score based on simulation health."""
    health = coverage_report.health

    # Check error counts
    if health.uvm_fatals > acceptance.max_uvm_fatals:
        return 0.0  # Fatal errors = instant fail

    if health.uvm_errors > acceptance.max_uvm_errors:
        error_penalty = (health.uvm_errors - acceptance.max_uvm_errors) * 20
        score = max(0.0, 100.0 - error_penalty)
    else:
        score = 100.0

    # Check scoreboard
    if health.scoreboard_errors > acceptance.max_scoreboard_errors:
        score *= 0.5  # 50% penalty for scoreboard errors

    # Check assertions
    if acceptance.all_assertions_pass and health.assertion_failures > 0:
        score *= 0.5  # 50% penalty for assertion failures

    # Timeout penalty
    if health.simulation_timeout:
        score *= 0.25  # 75% penalty for timeout

    return score
```

## Pass/Fail Determination

A solution **passes** if:
```python
def determine_pass(eval_result, acceptance):
    # Must meet minimum thresholds
    functional_pass = (
        eval_result.functional_score >=
        acceptance.functional_min_pct
    )

    code_pass = (
        eval_result.code_coverage_score >=
        min(acceptance.code_statements_min_pct,
            acceptance.code_branches_min_pct)
    )

    health_pass = (
        eval_result.health_score >= 50.0 and
        coverage_report.health.uvm_fatals == 0
    )

    return functional_pass and code_pass and health_pass
```

## Example Evaluation

### Task Specification

```markdown
## Acceptance Criteria

### Functional Coverage
- Minimum: 80.0%
- Target bins:
  - `apb_coverage.cp_pdata.pdata_8b`
  - `apb_coverage.cp_paddr.addr_low`

### Code Coverage
- Statements: ≥70.0%
- Branches: ≥60.0%
- Toggles: ≥50.0%

### Health
- UVM Errors: ≤0
- UVM Fatals: ≤0
- Scoreboard Errors: ≤0

### Scoring Weights
- Functional Coverage: 60.0%
- Code Coverage: 30.0%
- Health: 10.0%
```

### Coverage Results

**Functional Coverage:**
- `apb_coverage.cp_pdata.pdata_8b`: Hits=100, Goal=10 ✓ Covered
- `apb_coverage.cp_paddr.addr_low`: Hits=50, Goal=10 ✓ Covered
- Overall: 85.5%
- **Score: 100.0** (both bins covered)

**Code Coverage:**
- Statements: 75.5% (target: 70%) → 107.9/100 = 100.0
- Branches: 68.3% (target: 60%) → 113.8/100 = 100.0
- Toggles: 55.0% (target: 50%) → 110.0/100 = 100.0
- **Score: 100.0** (average)

**Health:**
- UVM Errors: 0 (target: ≤0) ✓
- UVM Fatals: 0 (target: ≤0) ✓
- Scoreboard Errors: 0 (target: ≤0) ✓
- **Score: 100.0** (perfect health)

### Final Score

```
Total Score = (100.0 × 0.6) + (100.0 × 0.3) + (100.0 × 0.1)
           = 60.0 + 30.0 + 10.0
           = 100.0
```

**Result: PASSED** (all thresholds met, perfect score)

## Evaluation Output

### Console Output

```
[Evaluator] Task: task_001_8b_write
[Evaluator] Applying patch: solution.patch
[Evaluator] Patch applied successfully
[Evaluator] Compiling design with Xcelium...
[Xcelium] Compilation successful
[Evaluator] Running simulation...
[Evaluator] Simulation completed in 12.5s
[Evaluator] Extracting coverage from: cov_work
[Evaluator] Parsing functional coverage...
[Evaluator]   Found 2 covergroups
[Evaluator]   Target bins covered: 2/2
[Evaluator] Parsing code coverage...
[Evaluator]   Statements: 75.5%
[Evaluator]   Branches: 68.3%
[Evaluator]   Toggles: 55.0%
[Evaluator] Analyzing health metrics...
[Evaluator]   UVM Errors: 0
[Evaluator]   UVM Fatals: 0
[Evaluator]   Scoreboard: PASS
[Evaluator]
[Evaluator] ======== EVALUATION RESULTS ========
[Evaluator] Task: task_001_8b_write
[Evaluator] Status: PASSED
[Evaluator] Total Score: 100.0/100
[Evaluator]
[Evaluator] Component Scores:
[Evaluator]   Functional Coverage: 100.0/100 (weight: 60%)
[Evaluator]   Code Coverage:       100.0/100 (weight: 30%)
[Evaluator]   Health:              100.0/100 (weight: 10%)
[Evaluator]
[Evaluator] Weighted Contributions:
[Evaluator]   Functional: 60.0 points
[Evaluator]   Code:       30.0 points
[Evaluator]   Health:     10.0 points
[Evaluator] ====================================
```

### JSON Output

```bash
tb run --dataset-path <tasks_dir> --task-id <task-id> --output-path runs
```

```json
{
  "task_id": "task_001_8b_write",
  "passed": true,
  "score": 100.0,
  "functional_score": 100.0,
  "code_coverage_score": 100.0,
  "health_score": 100.0,
  "functional_bins_met": [
    "apb_coverage.cp_pdata.pdata_8b",
    "apb_coverage.cp_paddr.addr_low"
  ],
  "functional_bins_missed": [],
  "thresholds_met": {
    "functional_min": true,
    "code_statements_min": true,
    "code_branches_min": true,
    "health": true
  },
  "coverage_details": {
    "functional": {
      "overall_pct": 85.5,
      "covergroups": [
        {
          "name": "apb_coverage",
          "bins": [
            {"name": "pdata_8b", "hits": 100, "goal": 10, "covered": true},
            {"name": "addr_low", "hits": 50, "goal": 10, "covered": true}
          ]
        }
      ]
    },
    "code": {
      "statements_pct": 75.5,
      "branches_pct": 68.3,
      "toggles_pct": 55.0
    },
    "health": {
      "uvm_errors": 0,
      "uvm_fatals": 0,
      "scoreboard_errors": 0,
      "assertion_failures": 0
    }
  },
  "simulation": {
    "runtime_sec": 12.5,
    "timed_out": false,
    "log_path": "artifacts/task_001/simulation.log",
    "coverage_db_path": "artifacts/task_001/cov_work"
  }
}
```

## Advanced Topics

### Custom Scoring Functions

You can implement custom scoring functions:

```python
from dvsmith.harness.evaluator import Evaluator

class CustomEvaluator(Evaluator):
    def _score_functional(self, coverage, acceptance):
        """Custom functional coverage scoring."""
        # Your custom logic
        return custom_score
```

### Multi-Simulator Evaluation

```bash
# Run on multiple simulators and compare
for sim in xcelium questa vcs; do
    tb run --dataset-path <tasks_dir> --task-id <task-id> --output-path "runs/${sim}"
done

# Compare results
python compare_results.py results_*.json
```

### Regression Testing

```bash
# Evaluate on entire benchmark suite
for task in gym/tasks/*.md; do
    task_id=$(basename "$task" .md)
    tb run --dataset-path <tasks_dir> --task-id "$task_id" --output-path "runs/${task_id}"
done

# Generate summary report
python generate_report.py results/*.json
```

## Troubleshooting

### Issue: Score is 0 despite passing simulation

**Check:**
1. Coverage database was generated
2. Coverage files are being parsed correctly
3. Target bins match actual covergroup/bin names

### Issue: Health score is low

**Check simulation log for:**
- UVM_ERROR messages
- Scoreboard mismatches
- Assertion failures
- Use: `grep -E "(UVM_ERROR|UVM_FATAL)" simulation.log`

### Issue: Code coverage not improving

**Hints:**
- Add more transactions to sequence
- Vary transaction parameters
- Exercise error conditions
- Toggle signals in both directions

## Next Steps

- **[Advanced Evaluation](04_advanced_evaluation.md)**: Custom metrics, multi-objective optimization
- **[Benchmark Creation](05_creating_benchmarks.md)**: Build your own DV gyms
