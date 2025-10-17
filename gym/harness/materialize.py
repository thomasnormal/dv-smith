#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GYM_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARENA_ROOT = os.path.join(REPO_ROOT, "arena")


def load_task(task_id: str):
    tasks_dir = os.path.join(GYM_ROOT, "tasks")
    path = os.path.join(tasks_dir, f"{task_id}.yaml")
    if not os.path.exists(path):
        raise SystemExit(f"Task not found: {task_id} ({path})")
    with open(path) as f:
        return yaml.safe_load(f)


def list_tasks():
    tasks_dir = os.path.join(GYM_ROOT, "tasks")
    for fn in sorted(os.listdir(tasks_dir)):
        if not fn.endswith(".yaml"): continue
        with open(os.path.join(tasks_dir, fn)) as f:
            data = yaml.safe_load(f)
        print(f"{data['id']}: {data['title']}")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def copy_file(src, dst):
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)


def write_text(path, content: str):
    ensure_dir(os.path.dirname(path))
    with open(path, "w") as f:
        f.write(content)


def materialize_t1(task):
    arena = os.path.join(ARENA_ROOT, task['id'])
    # Clean arena
    if os.path.exists(arena):
        shutil.rmtree(arena)
    ensure_dir(arena)

    # Copy stub and eval files
    copy_file(os.path.join(REPO_ROOT, "gym/stubs/master_assertions.sv"),
              os.path.join(arena, "src/hdl_top/master_assertions.sv"))
    copy_file(os.path.join(REPO_ROOT, "src/hdl_top/tb_master_assertions.sv"),
              os.path.join(arena, "src/hdl_top/tb_master_assertions.sv"))
    copy_file(os.path.join(REPO_ROOT, "gym/eval/assertions_master_eval_top.sv"),
              os.path.join(arena, "src/hdl_top/assertions_master_eval_top.sv"))
    # Makefile for questa
    copy_file(os.path.join(REPO_ROOT, "gym/harness/templates/questa_assertions_makefile"),
              os.path.join(arena, "sim/questasim/Makefile"))

    # Write arena info
    write_text(os.path.join(arena, "ARENA_INFO.txt"),
               "Task: t1_master_assertions\nEdit: src/hdl_top/master_assertions.sv\nRun: (cd sim/questasim && make)\n")
    print(f"Materialized arena at {arena}")


def materialize_t2(task):
    arena = os.path.join(ARENA_ROOT, task['id'])
    if os.path.exists(arena):
        shutil.rmtree(arena)
    ensure_dir(arena)

    # Place stub coverage file to be implemented by the agent
    copy_file(os.path.join(REPO_ROOT, "gym/stubs/axi4_master_coverage.sv"),
              os.path.join(arena, "src/hvl_top/master/axi4_master_coverage.sv"))
    # Place eval test class
    copy_file(os.path.join(REPO_ROOT, "gym/eval/coverage_eval_test.sv"),
              os.path.join(arena, "src/hvl_top/test/coverage_eval_test.sv"))

    # Provide a minimal axi4_test_pkg that includes base_test and our eval test
    test_pkg = (
        "`ifndef AXI4_TEST_PKG_INCLUDED_\n"
        "`define AXI4_TEST_PKG_INCLUDED_\n\n"
        "package axi4_test_pkg;\n"
        "  `include \"uvm_macros.svh\"\n"
        "  import uvm_pkg::*;\n"
        "  import axi4_globals_pkg::*;\n"
        "  import axi4_master_pkg::*;\n"
        "  import axi4_slave_pkg::*;\n"
        "  import axi4_env_pkg::*;\n"
        "  import axi4_master_seq_pkg::*;\n"
        "  import axi4_slave_seq_pkg::*;\n"
        "  import axi4_virtual_seq_pkg::*;\n"
        "  `include \"axi4_base_test.sv\"\n"
        "  `include \"coverage_eval_test.sv\"\n"
        "endpackage : axi4_test_pkg\n\n"
        "`endif\n"
    )
    write_text(os.path.join(arena, "src/hvl_top/test/axi4_test_pkg.sv"), test_pkg)

    # Generate a compile.f local to arena using the repo sources except for coverage and tests
    compile_f = []
    add = compile_f.append
    add("+incdir+../../src/globals/")
    add("+incdir+../../src/hvl_top/test/sequences/master_sequences/")
    add("+incdir+../../src/hvl_top/master/")
    add("+incdir+../../src/hdl_top/master_agent_bfm/")
    add("+incdir+../../src/hvl_top/env/virtual_sequencer/")
    add("+incdir+../../src/hvl_top/test/virtual_sequences/")
    add("+incdir+../../src/hvl_top/env")
    add("+incdir+../../src/hvl_top/slave")
    add("+incdir+../../src/hvl_top/test/sequences/slave_sequences/")
    add("+incdir+../../src/hdl_top/slave_agent_bfm")
    add("+incdir+../../src/hdl_top/axi4_interface")
    add("+incdir+../src/hvl_top/test")  # arena-local test pkg dir (for includes)
    add("../../src/globals/axi4_globals_pkg.sv")
    add("../../src/hvl_top/master/axi4_master_pkg.sv")
    add("../../src/hvl_top/slave/axi4_slave_pkg.sv")
    add("../../src/hvl_top/test/sequences/master_sequences/axi4_master_seq_pkg.sv")
    add("../../src/hvl_top/test/sequences/slave_sequences/axi4_slave_seq_pkg.sv")
    add("../../src/hvl_top/env/axi4_env_pkg.sv")
    add("../../src/hvl_top/test/virtual_sequences/axi4_virtual_seq_pkg.sv")
    add("../../src/hdl_top/axi4_interface/axi4_if.sv")
    add("../../src/hdl_top/master_agent_bfm/axi4_master_driver_bfm.sv")
    add("../../src/hdl_top/master_agent_bfm/axi4_master_monitor_bfm.sv")
    add("../../src/hdl_top/master_agent_bfm/axi4_master_agent_bfm.sv")
    add("../../src/hdl_top/slave_agent_bfm/axi4_slave_driver_bfm.sv")
    add("../../src/hdl_top/slave_agent_bfm/axi4_slave_monitor_bfm.sv")
    add("../../src/hdl_top/slave_agent_bfm/axi4_slave_agent_bfm.sv")
    add("../../src/hdl_top/hdl_top.sv")
    add("../../src/hvl_top/hvl_top.sv")
    # Agent-provided coverage (arena path)
    add("../src/hvl_top/master/axi4_master_coverage.sv")
    # Arena-local test package
    add("../src/hvl_top/test/axi4_test_pkg.sv")

    compile_f_path = os.path.join(arena, "sim/axi4_compile.f")
    ensure_dir(os.path.dirname(compile_f_path))
    write_text(compile_f_path, "\n".join(compile_f) + "\n")

    # Copy the Questasim makefile
    copy_file(os.path.join(REPO_ROOT, "sim/questasim/makefile"),
              os.path.join(arena, "sim/questasim/makefile"))

    write_text(os.path.join(arena, "ARENA_INFO.txt"),
               "Task: t2_master_coverage\nEdit: src/hvl_top/master/axi4_master_coverage.sv\nRun: (cd sim/questasim && make compile && make simulate test=coverage_eval_test uvm_verbosity=UVM_LOW)\n")
    print(f"Materialized arena at {arena}")


def main():
    ap = argparse.ArgumentParser(description="Materialize a clean arena for an agent gym task")
    ap.add_argument("--task", help="Task id (e.g., t1_master_assertions)")
    ap.add_argument("--list", action="store_true", help="List available tasks")
    args = ap.parse_args()

    if args.list:
        list_tasks()
        return

    if not args.task:
        ap.error("--task is required unless --list is specified")

    task = load_task(args.task)
    tid = task["id"]
    if tid == "t1_master_assertions":
        materialize_t1(task)
    elif tid == "t2_master_coverage":
        materialize_t2(task)
    else:
        raise SystemExit(f"Unsupported task id: {tid}")


if __name__ == "__main__":
    main()

