#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
from coverage_utils import parse_coverage_text, diff_bins, weighted_jaccard


def simulate(questasim_dir, test, seed, args_str, folder):
    subprocess.run(["make", "simulate",
                    f"test={test}", f"uvm_verbosity=UVM_LOW", f"seed={seed}", f"test_folder={folder}"],
                   cwd=questasim_dir, check=True)
    return os.path.join(questasim_dir, folder, "coverage.txt"), os.path.join(questasim_dir, folder, f"{test}.log")


def main():
    ap = argparse.ArgumentParser(description="Check test coverage signature similarity vs ground truth")
    ap.add_argument("test")
    ap.add_argument("signature", help="Path to ground-truth signature JSON for this test")
    ap.add_argument("--baseline", default="gym/signatures/_baseline.json")
    ap.add_argument("--seed", default="12345")
    ap.add_argument("--args", default="+DATA_WIDTH=32")
    ap.add_argument("--threshold", type=float, default=0.7)
    args = ap.parse_args()

    questasim_dir = os.path.join("sim", "questasim")

    # Compile once if needed
    subprocess.run(["make", "compile", f"args={args.args}"], cwd=questasim_dir, check=True)

    cov_path, log_path = simulate(questasim_dir, args.test, args.seed, args.args, args.test)

    # Basic log health check
    with open(log_path, 'r', errors='ignore') as f:
        log = f.read()
    if any(x in log for x in ["UVM_FATAL", "UVM_ERROR", " Error"]):
        print("FAIL: log contains errors")
        raise SystemExit(2)

    # Load baseline and ground truth signature
    with open(args.baseline) as f:
        base_bins = json.load(f)
    with open(args.signature) as f:
        truth_sig = json.load(f)

    # Compute submission signature
    bins = parse_coverage_text(cov_path)
    sig = diff_bins(bins, base_bins)

    score = weighted_jaccard(sig, truth_sig)
    print(f"similarity={score:.3f}")
    if score >= args.threshold:
        print("PASS")
        raise SystemExit(0)
    else:
        print("FAIL: below threshold")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

