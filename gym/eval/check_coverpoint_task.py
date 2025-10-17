#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from coverage_utils import parse_coverage_text


def main():
    ap = argparse.ArgumentParser(description="Check presence and hits for specified coverpoint bins")
    ap.add_argument("test", help="UVM test name to run")
    ap.add_argument("--coverpoint", required=True, help="Coverpoint name as shown in vcover text")
    ap.add_argument("--bins", nargs='+', required=True, help="Bin names to require (hit >= min_hits)")
    ap.add_argument("--min_hits", type=int, default=1)
    ap.add_argument("--seed", default="12345")
    ap.add_argument("--args", default="+DATA_WIDTH=32")
    ap.add_argument("--uvm_verbosity", default="UVM_LOW")
    args = ap.parse_args()

    questasim_dir = os.path.join("sim", "questasim")
    subprocess.run(["make", "compile", f"args={args.args}"], cwd=questasim_dir, check=True)

    # Run the test
    folder = args.test
    subprocess.run(["make", "simulate", f"test={args.test}", f"uvm_verbosity={args.uvm_verbosity}", f"seed={args.seed}", f"test_folder={folder}"], cwd=questasim_dir, check=True)

    cov_path = os.path.join(questasim_dir, folder, "coverage.txt")
    if not os.path.exists(cov_path):
        print("FAIL: missing coverage.txt")
        sys.exit(2)

    bins = parse_coverage_text(cov_path)

    missing = []
    for b in args.bins:
        key = f"{args.coverpoint}.{b}"
        hits = bins.get(key, 0)
        if hits < args.min_hits:
            missing.append((key, hits))

    if missing:
        for key, hits in missing:
            print(f"MISS {key} hits={hits}")
        print("FAIL")
        sys.exit(1)
    else:
        print("PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()

