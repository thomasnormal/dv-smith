#!/usr/bin/env python3
import argparse
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser(description="Static check: required assertion/cover property present with expected structure")
    ap.add_argument("--file", default="src/hdl_top/master_assertions.sv")
    ap.add_argument("--property_name", required=True)
    ap.add_argument("--must_contain", nargs='+', default=[], help="Regex snippets that must appear within the property block")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print("FAIL: file not found", args.file)
        sys.exit(2)

    with open(args.file, 'r', errors='ignore') as f:
        txt = f.read()

    # Roughly isolate the property block by name
    m = re.search(rf"property\s+{re.escape(args.property_name)}\s*;([\s\S]*?)endproperty", txt, re.MULTILINE)
    if not m:
        print("FAIL: property not found", args.property_name)
        sys.exit(1)

    body = m.group(1)
    for pat in args.must_contain:
        if not re.search(pat, body):
            print("FAIL: missing snippet:", pat)
            sys.exit(1)

    print("PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()

