Task Runner Framework
=====================

This repository includes a lightweight task framework for authoring and evaluating UVM/HDL tasks.
Tasks are single files with a `.task.yaml` extension and the following schema:

meta:
  id: unique_id
  category: test_case | coverage_code | assertion | closure
  scoring: pass_fail
  simulators: ['questa'|'xcellium'|...]
description: |
  Markdown shown to the agent describing what to implement.
root:
  type: git
  url: git@github.com:org/repo.git (or '.')
  commit: <sha>
  patch: |
    *** Begin Patch
    ... optional pre-authoring patch (minimal ‘apply_patch’ envelope)
    *** End Patch
scope:
  allowed_edits:
    - src/hvl_top
eval:
  timeout: 60
  patch: |
    *** Begin Patch
    ... optional pre-eval patch
    *** End Patch
  python: |
    Plain Python eval code that compiles/runs and prints PASS/FAIL.
expected_patch: |
  *** Begin Patch
  ... example solution patch for reference
  *** End Patch

Runner
------

Use `gym/run_task.py` to execute a task inside a fresh git worktree at the declared commit. It
applies `root.patch`, overlays files the agent changed (limited to `scope.allowed_edits`) from your
current working directory, applies `eval.patch`, then executes the eval.python with the configured
timeout.

Example:

  python3 gym/run_task.py gym/tasks/seq_fixed_16b.task.yaml

Notes
-----
- The built-in patch applier currently supports `*** Add File` in the minimal envelope. More complex
  updates can be handled by leaving root/eval patches blank or using unified diffs in future.
- The eval code can optionally `from dvsmith.harness import report_result` to emit structured
  PASS/FAIL output. A minimal fallback is provided when the import is not available.
- For Questa-based tasks, the makefile `sim/questasim/makefile` emits a parseable `coverage.txt`.
- For Xcelium-based tasks, use `sim/cadence_sim/makefile` and parse coverage numbers from the log or
  integrate an IMC report step.

