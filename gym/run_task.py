#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import sys
import tempfile

# Local harness
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from dvsmith.harness import (
    report_result,
    make_worktree_at_commit,
    apply_patch_envelope,
    copy_allowed_edits,
    write_and_run_eval_python,
)


def parse_simple_task_yaml(path: str) -> dict:
    """Parse the specific task YAML-like format into a dict without external deps.

    Supports top-level keys: meta, description, root, scope, eval, expected_patch.
    Each can contain simple scalars, list of strings, and block strings via "|".
    """
    with open(path, 'r') as f:
        lines = f.read().splitlines()
    i = 0
    def peek():
        return lines[i] if i < len(lines) else None
    def consume():
        nonlocal i
        val = lines[i]
        i += 1
        return val
    def parse_block(indent):
        buf = []
        while i < len(lines):
            ln = lines[i]
            if ln.strip() == '':
                buf.append('')
                i += 1
                continue
            cur_indent = len(ln) - len(ln.lstrip(' '))
            if cur_indent < indent:
                break
            buf.append(ln[indent:])
            i += 1
        return "\n".join(buf).rstrip() + "\n"
    def parse_mapping(indent):
        m = {}
        while i < len(lines):
            ln = lines[i]
            if ln.strip() == '':
                i += 1
                continue
            cur_indent = len(ln) - len(ln.lstrip(' '))
            if cur_indent < indent:
                break
            if re.match(r"^[A-Za-z0-9_]+:\s*\|\s*$", ln.strip()):
                key = ln.strip().split(':', 1)[0]
                i += 1
                m[key] = parse_block(cur_indent + 2)
            elif re.match(r"^[A-Za-z0-9_]+:\s*$", ln.strip()):
                key = ln.strip()[:-1]
                i += 1
                # Determine if next line is list or mapping or scalar
                if i < len(lines) and re.match(r"^\s*-\s+", lines[i]):
                    lst = []
                    while i < len(lines) and re.match(r"^\s*-\s+", lines[i]):
                        item = re.sub(r"^\s*-\s+", "", lines[i])
                        lst.append(item)
                        i += 1
                    m[key] = lst
                elif i < len(lines) and (len(lines[i]) - len(lines[i].lstrip(' '))) > cur_indent:
                    # nested mapping
                    m[key] = parse_mapping(cur_indent + 2)
                else:
                    m[key] = None
            else:
                # key: value on same line
                mat = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", ln.strip())
                if not mat:
                    break
                key, val = mat.group(1), mat.group(2)
                # lists like ['xcellium']
                if val.startswith('[') and val.endswith(']'):
                    inner = val[1:-1].strip()
                    m[key] = [s.strip().strip("'\"") for s in inner.split(',') if s.strip()]
                else:
                    m[key] = val.strip().strip("'\"")
                i += 1
        return m

    task = parse_mapping(0)
    return task


def main():
    ap = argparse.ArgumentParser(description="Run a single task file")
    ap.add_argument("task_file", help="Path to *.task.yaml")
    ap.add_argument("--use-current", action="store_true", help="Run eval in current repo instead of worktree")
    args = ap.parse_args()

    task = parse_simple_task_yaml(args.task_file)
    meta = task.get('meta', {})
    root = task.get('root', {})
    scope = task.get('scope', {})
    evalsec = task.get('eval', {})

    # Prepare workspace
    commit = (root.get('commit') or '').strip()
    if args.use_current:
        workdir = os.getcwd()
    else:
        base = tempfile.mkdtemp(prefix=f"task_{meta.get('id','task')}_")
        try:
            workdir = os.path.join(base, 'worktree')
            make_worktree_at_commit(commit, workdir)
        except Exception as e:
            report_result(False, {"stage": "worktree"}, f"{e}")
            sys.exit(2)

    # Apply root.patch
    if isinstance(root.get('patch'), str) and root['patch'].strip():
        try:
            apply_patch_envelope(root['patch'], workdir)
        except Exception as e:
            report_result(False, {"stage": "root.patch"}, f"{e}")
            sys.exit(3)

    # Overlay allowed edits from current repo into workdir
    if not args.use_current and isinstance(scope.get('allowed_edits'), list):
        copy_allowed_edits(os.getcwd(), workdir, scope['allowed_edits'])

    # Apply eval.patch
    if isinstance(evalsec.get('patch'), str) and evalsec['patch'].strip():
        try:
            apply_patch_envelope(evalsec['patch'], workdir)
        except Exception as e:
            report_result(False, {"stage": "eval.patch"}, f"{e}")
            sys.exit(4)

    # Write and run eval python
    timeout = None
    try:
        timeout = int(evalsec.get('timeout') or 0) or None
    except Exception:
        timeout = None
    code = evalsec.get('python') or ''
    if not code.strip():
        report_result(False, {"stage": "eval"}, "no eval.python provided")
        sys.exit(5)

    # Ensure our harness is importable by eval code
    lib_path = os.path.join(os.path.dirname(__file__), 'lib')
    env = os.environ.copy()
    env['PYTHONPATH'] = lib_path + os.pathsep + env.get('PYTHONPATH', '')
    rc, out = write_and_run_eval_python(code, cwd=workdir, timeout=timeout, extra_env=env)
    print(out)
    # Best-effort parse of a PASS/FAIL marker
    if rc == 0 and re.search(r"\bPASS\b", out):
        sys.exit(0)
    sys.exit(rc if rc != 0 else 1)


if __name__ == "__main__":
    main()

