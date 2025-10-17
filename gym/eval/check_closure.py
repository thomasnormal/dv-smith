#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import time


def run_make_sim(test, seed, uvm_verbosity, folder, timeout_s):
    questasim_dir = os.path.join("sim", "questasim")
    cmd = ["make", "simulate", f"test={test}", f"uvm_verbosity={uvm_verbosity}", f"seed={seed}", f"test_folder={folder}"]
    start = time.time()
    try:
        subprocess.run(cmd, cwd=questasim_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        print("FAIL: simulation timeout", file=sys.stderr)
        return None, None, True
    dur = time.time() - start
    log_path = os.path.join(questasim_dir, folder, f"{test}.log")
    return log_path, dur, False


def parse_cov_from_log(log_path):
    with open(log_path, 'r', errors='ignore') as f:
        txt = f.read()
    # Master and Slave coverage are printed in report_phase of coverage components
    mm = re.search(r"AXI4 Master Agent Coverage\s*=\s*([0-9]+\.?[0-9]*)\s*%", txt)
    ms = re.search(r"AXI4 Slave Agent Coverage\s*=\s*([0-9]+\.?[0-9]*)\s*%", txt)
    m = float(mm.group(1)) if mm else 0.0
    s = float(ms.group(1)) if ms else 0.0
    return m, s


def main():
    ap = argparse.ArgumentParser(description="Check coverage closure within time budget")
    ap.add_argument("test", help="Name of a single orchestrating test to run")
    ap.add_argument("--threshold", type=float, default=40.0, help="Minimum average( master, slave ) coverage percent")
    ap.add_argument("--timeout_s", type=int, default=60, help="Wall clock time budget for the simulation")
    ap.add_argument("--seed", default="12345")
    ap.add_argument("--uvm_verbosity", default="UVM_LOW")
    ap.add_argument("--args", default="+DATA_WIDTH=32")
    args = ap.parse_args()

    questasim_dir = os.path.join("sim", "questasim")
    # Compile
    subprocess.run(["make", "clean_compile"], cwd=questasim_dir, check=False)
    r = subprocess.run(["make", "compile", f"args={args.args}"], cwd=questasim_dir)
    if r.returncode != 0:
        print("FAIL: compile")
        sys.exit(2)

    log_path, dur, timed_out = run_make_sim(args.test, args.seed, args.uvm_verbosity, args.test, args.timeout_s)
    if timed_out or not log_path or not os.path.exists(log_path):
        print("FAIL: sim not completed within budget or missing log")
        sys.exit(3)

    with open(log_path, 'r', errors='ignore') as f:
        log = f.read()
    if re.search(r"UVM_FATAL|UVM_ERROR|\bError\b", log):
        print("FAIL: log errors present")
        sys.exit(4)

    m, s = parse_cov_from_log(log_path)
    avg = (m + s) / 2.0
    print(f"master_cov={m:.2f}% slave_cov={s:.2f}% avg={avg:.2f}% duration_s={dur:.1f}")
    if avg >= args.threshold:
        print("PASS")
        sys.exit(0)
    else:
        print("FAIL: below threshold")
        sys.exit(1)


if __name__ == "__main__":
    main()

