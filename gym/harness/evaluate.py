#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARENA_ROOT = os.path.join(REPO_ROOT, "arena")


def run(cmd, cwd=None):
    print(f"$ {' '.join(cmd)}", flush=True)
    res = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(res.stdout)
    if res.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)} (rc={res.returncode})")
    return res


def load_task(task_id):
    with open(os.path.join(REPO_ROOT, "gym/tasks", f"{task_id}.yaml")) as f:
        return yaml.safe_load(f)


def eval_t1(task_id, task):
    arena = os.path.join(ARENA_ROOT, task_id)
    questasim = os.path.join(arena, "sim/questasim")
    run(["make"], cwd=questasim)
    log = os.path.join(questasim, "sim.log")
    if not os.path.exists(log):
        raise SystemExit(f"Missing log: {log}")
    data = open(log).read()

    # Check each expected label appears at least once as ASSERT:<LABEL>
    labels = task["eval"]["expected_assert_labels"]
    missing = []
    for lbl in labels:
        if re.search(rf"ASSERT:{re.escape(lbl)}", data) is None:
            missing.append(lbl)
    if missing:
        print("FAIL: Missing assertion failures for labels:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(2)

    # Basic sanity: no UVM_FATAL or UVM_ERROR
    if re.search(r"UVM_FATAL|UVM_ERROR", data):
        print("FAIL: UVM errors detected in sim.log")
        sys.exit(2)

    print("PASS: All expected assertion failures observed on negative cases.")


def eval_t2(task_id, task):
    arena = os.path.join(ARENA_ROOT, task_id)
    questasim = os.path.join(arena, "sim/questasim")
    # Compile and simulate with our eval test
    run(["make", "clean_compile"], cwd=questasim)
    run(["make", "compile"], cwd=questasim)
    run(["make", "clean_simulate"], cwd=questasim)
    test_folder = "eval_run"
    run(["make", "simulate", f"test={task['eval']['testname']}", "uvm_verbosity=UVM_LOW", f"test_folder={test_folder}"], cwd=questasim)
    log = os.path.join(questasim, test_folder, f"{task['eval']['testname']}.log")
    if not os.path.exists(log):
        raise SystemExit(f"Missing log: {log}")
    data = open(log).read()

    # No UVM_FATAL/UVM_ERROR
    if re.search(r"UVM_FATAL|UVM_ERROR", data):
        print("FAIL: UVM errors detected in simulation log")
        sys.exit(2)

    # Extract coverage percentage printed by report_phase
    m = re.search(r"AXI4 Master Agent Coverage =\s*([0-9]+\.[0-9]+)\s*%", data)
    if not m:
        print("FAIL: Could not find coverage percentage in log")
        sys.exit(2)
    cov = float(m.group(1))
    print(f"Coverage reported: {cov:.2f}%")
    if cov < 60.0:
        print("FAIL: Coverage threshold not met (>= 60.0% required)")
        sys.exit(2)

    print("PASS: Coverage threshold met and no UVM errors.")


def main():
    ap = argparse.ArgumentParser(description="Evaluate a materialized agent gym task")
    ap.add_argument("--task", required=True, help="Task id (e.g., t1_master_assertions)")
    args = ap.parse_args()

    task = load_task(args.task)
    if args.task == "t1_master_assertions":
        eval_t1(args.task, task)
    elif args.task == "t2_master_coverage":
        eval_t2(args.task, task)
    else:
        raise SystemExit(f"Unsupported task id: {args.task}")


if __name__ == "__main__":
    main()

