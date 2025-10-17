#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys


def run(cmd, cwd=None):
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout


def main():
    ap = argparse.ArgumentParser(description="Evaluate a single AXI4 test by log and coverage checks")
    ap.add_argument("test", help="UVM test name, e.g. axi4_blocking_fixed_16b_write_read_test")
    ap.add_argument("--uvm_verbosity", default="UVM_LOW")
    ap.add_argument("--args", default="+DATA_WIDTH=32")
    ap.add_argument("--seed", default="random")
    ap.add_argument("--baseline_test", default="axi4_base_test",
                    help="Baseline test expected NOT to show the target evidence")
    ap.add_argument("--compile_only", action="store_true")
    args = ap.parse_args()

    questasim_dir = os.path.join("sim", "questasim")

    rc, out = run(["make", "clean_compile"], cwd=questasim_dir)
    rc, out = run(["make", "compile", f"args={args.args}"], cwd=questasim_dir)
    if rc != 0:
        print("compile_failed", flush=True)
        print(out)
        sys.exit(2)

    if args.compile_only:
        print("compile_pass", flush=True)
        sys.exit(0)

    # Optional: run a baseline control to ensure patterns are absent
    if args.baseline_test:
        baseline_folder = f"baseline_{args.baseline_test}"
        rc, out = run(["make", "simulate",
                       f"test={args.baseline_test}",
                       f"uvm_verbosity={args.uvm_verbosity}",
                       f"seed={args.seed}",
                       f"test_folder={baseline_folder}"], cwd=questasim_dir)
        baseline_log_path = os.path.join(questasim_dir, baseline_folder, f"{args.baseline_test}.log")
        if os.path.exists(baseline_log_path):
            with open(baseline_log_path, "r", errors="ignore") as f:
                base_log = f.read()
            # Same scoreboard evidence patterns we require later must be absent here
            baseline_bad = False
            for pat in [
                r"SB_awburst_MATCHED .* 'h0",
                r"SB_arburst_MATCHED .* 'h0",
                r"SB_awsize_MATCHED .* 'h1",
                r"SB_arsize_MATCHED .* 'h1",
                r"SB_wdata_MATCHED",
                r"SB_rdata_MATCHED",
            ]:
                if re.search(pat, base_log):
                    print("baseline_pattern_present:", pat)
                    baseline_bad = True
            if baseline_bad:
                sys.exit(8)

    test_folder = args.test
    rc, out = run(["make", "simulate", f"test={args.test}", f"uvm_verbosity={args.uvm_verbosity}", f"seed={args.seed}", f"test_folder={test_folder}"], cwd=questasim_dir)
    # Always run simulate_war_err in the makefile; we'll parse log too.

    log_path = os.path.join(questasim_dir, test_folder, f"{args.test}.log")
    cov_path = os.path.join(questasim_dir, test_folder, "coverage.txt")

    # Basic log health
    if not os.path.exists(log_path):
        print("missing_log", log_path)
        sys.exit(3)

    with open(log_path, "r", errors="ignore") as f:
        log = f.read()

    # Fail on any simulator/uvm errors
    if re.search(r"UVM_FATAL|UVM_ERROR|\bError\b", log):
        print("log_errors_found")
        sys.exit(4)

    # Scoreboard evidence: ensure fixed burst (awburst/arburst == 0) and 16b (awsize/arsize == 1), plus data matched
    needs = {
        "SB_awburst_MATCHED .* 'h0": False,
        "SB_arburst_MATCHED .* 'h0": False,
        "SB_awsize_MATCHED .* 'h1": False,
        "SB_arsize_MATCHED .* 'h1": False,
        "SB_wdata_MATCHED": False,
        "SB_rdata_MATCHED": False,
    }
    for pat in list(needs.keys()):
        if re.search(pat, log):
            needs[pat] = True

    missing = [k for k, v in needs.items() if not v]
    if missing:
        print("scoreboard_evidence_missing:", ", ".join(missing))
        sys.exit(5)

    # Coverage bins: AWSIZE 2 bytes and ARSIZE 2 bytes hit at least once
    if not os.path.exists(cov_path):
        print("missing_coverage_txt", cov_path)
        sys.exit(6)

    with open(cov_path, "r", errors="ignore") as f:
        cov = f.read()

    cov_needs = [
        r"AWSIZE_CP\s*:\s*.*",  # coverpoint present
        r"ARSIZE_CP\s*:\s*.*",
        r"AWSIZE_2BYTES",
        r"ARSIZE_2BYTES",
    ]
    for pat in cov_needs:
        if not re.search(pat, cov):
            print("coverage_bin_missing:", pat)
            sys.exit(7)

    print("PASS")

if __name__ == "__main__":
    main()
