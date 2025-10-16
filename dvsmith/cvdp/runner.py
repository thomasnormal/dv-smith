"""CVDP harness runner for Docker-based execution."""

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from .models import CvdpItem


def _docker_compose_cmd() -> list[str]:
    """Get docker compose command (prefer v2)."""
    return ["docker", "compose"]


def prepare_workspace(work_dir: Path, item: CvdpItem) -> Tuple[Path, Path]:
    """Prepare workspace for CVDP harness execution.
    
    Args:
        work_dir: Working directory
        item: CVDP item to prepare
        
    Returns:
        Tuple of (harness_root, code_root)
    """
    # Layout: work_dir/{harness,code}/...
    hdir = work_dir / "harness" / "src"
    cdir = work_dir / "code"
    (work_dir / "harness").mkdir(parents=True, exist_ok=True)
    hdir.mkdir(parents=True, exist_ok=True)
    (work_dir / "code" / "rundir").mkdir(parents=True, exist_ok=True)

    # Write harness files
    for rel, text in item.harness.items():
        out = work_dir / "harness" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        if out.name.endswith(".sh"):
            os.chmod(out, 0o755)

    # Write context files
    for rel, text in item.context.items():
        out = work_dir / "code" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)

    return hdir.parent.parent, cdir


def run_harness(
    work_dir: Path,
    item: CvdpItem,
    env: Optional[dict] = None
) -> Tuple[bool, Path]:
    """Run CVDP harness in Docker.
    
    Args:
        work_dir: Working directory
        item: CVDP item to run
        env: Optional environment variables
        
    Returns:
        Tuple of (success, log_path)
    """
    harness_root, _ = prepare_workspace(work_dir, item)
    dc = _docker_compose_cmd()
    log = work_dir / "harness.log"
    
    cmd = dc + [
        "-f", "harness/docker-compose.yml",
        "up",
        "--abort-on-container-exit",
        "--exit-code-from", "direct"
    ]
    
    with log.open("w") as lf:
        res = subprocess.run(
            cmd,
            cwd=work_dir,
            stdout=lf,
            stderr=subprocess.STDOUT,
            env={**os.environ, **(env or {})}
        )
    
    return (res.returncode == 0), log
