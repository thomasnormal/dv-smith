#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
from coverage_utils import parse_coverage_text, diff_bins


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def simulate(questasim_dir, test, seed, args_str, folder):
    subprocess.run(["make", "simulate",
                    f"test={test}", f"uvm_verbosity=UVM_LOW", f"seed={seed}", f"test_folder={folder}"],
                   cwd=questasim_dir, check=True)
    cov_path = os.path.join(questasim_dir, folder, "coverage.txt")
    return cov_path


def main():
    ap = argparse.ArgumentParser(description="Generate coverage signatures for tests vs baseline")
    ap.add_argument("--tests", nargs="*", help="List of tests to generate signatures for")
    ap.add_argument("--testlist", help="Optional path to testlist to read tests from", default="")
    ap.add_argument("--seed", default="12345")
    ap.add_argument("--args", default="+DATA_WIDTH=32")
    ap.add_argument("--outdir", default="gym/signatures")
    ap.add_argument("--baseline_test", default="axi4_base_test")
    args = ap.parse_args()

    questasim_dir = os.path.join("sim", "questasim")
    os.makedirs(args.outdir, exist_ok=True)

    # Compile once
    subprocess.run(["make", "clean_compile"], cwd=questasim_dir, check=True)
    subprocess.run(["make", "compile", f"args={args.args}"], cwd=questasim_dir, check=True)

    # Baseline simulation
    base_folder = f"baseline_{args.baseline_test}"
    base_cov = simulate(questasim_dir, args.baseline_test, args.seed, args.args, base_folder)
    base_bins = parse_coverage_text(base_cov)
    with open(os.path.join(args.outdir, "_baseline.json"), "w") as f:
        json.dump(base_bins, f, indent=2, sort_keys=True)

    tests = list(args.tests) if args.tests else []
    if args.testlist and os.path.exists(args.testlist):
        with open(args.testlist) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if re.search(r"_test\b", line):
                    tests.append(line)

    for t in tests:
        folder = t
        cov = simulate(questasim_dir, t, args.seed, args.args, folder)
        bins = parse_coverage_text(cov)
        sig = diff_bins(bins, base_bins)
        with open(os.path.join(args.outdir, f"{t}.json"), "w") as f:
            json.dump(sig, f, indent=2, sort_keys=True)
        print(f"Saved signature for {t}: {len(sig)} bins")


if __name__ == "__main__":
    main()

