.PHONY: compile run clean

SIM ?= xcelium
TEST ?= test_base_test

compile:
	@echo "Compiling test bench..."

run: compile
	@echo "Running test: $(TEST)"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf INCA_libs simv* csrc *.log *.key
