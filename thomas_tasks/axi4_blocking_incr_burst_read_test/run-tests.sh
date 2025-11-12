#!/bin/bash
# Terminal Bench test runner script
# This script is executed by Terminal Bench to run the tests

set -e

cd /tests

# Run pytest with the test file
# -rA: show extra test summary info for ALL outcomes including passes
# This is required for Terminal Bench's pytest parser to work
pytest test_outputs.py -v -s -rA
