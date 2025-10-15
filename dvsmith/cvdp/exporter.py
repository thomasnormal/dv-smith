"""Export dv-smith analysis to CVDP format."""

from pathlib import Path
from typing import List, Dict, Optional

from ..core.models import RepoAnalysis, UVMTest, Simulator
from .models import CvdpItem
from .harness_templates import harness_for_xcelium, harness_for_questa, harness_for_vcs


def _collect_context(repo_root: Path, rel_paths: List[Path]) -> Dict[str, str]:
    """Collect file contents for context.
    
    Args:
        repo_root: Repository root path
        rel_paths: List of relative paths to include
        
    Returns:
        Dict mapping relative paths to file contents
    """
    ctx: Dict[str, str] = {}
    for rp in rel_paths:
        p = (repo_root / rp).resolve()
        if p.exists() and p.is_file():
            rel = rp.as_posix()  # relative under /code
            try:
                ctx[rel] = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
    return ctx


def _system_message() -> str:
    """Generate system message for CVDP tasks."""
    return (
        "You can run shell commands (ls, tree, cat, echo, make, xrun/vsim). "
        "At the end, output a single-file Linux patch in a 'patch:' block."
    )


def _prompt_for_test(test: UVMTest, repo_root: Path) -> str:
    """Generate prompt for a specific test task.
    
    Args:
        test: UVM test to create task for
        repo_root: Repository root path
        
    Returns:
        Prompt string
    """
    rel_path = test.file_path.relative_to(repo_root)
    return (
        f"You must modify `/code/{rel_path}` (or a related file) so the verification harness passes. "
        f"This test verifies: {test.description or test.name}. "
        "Return a single-file Linux patch at the end."
    )


def build_cvdp_items(
    analysis: RepoAnalysis,
    prefer: Optional[Simulator] = None
) -> List[CvdpItem]:
    """Build CVDP items from repository analysis.
    
    Args:
        analysis: Repository analysis results
        prefer: Preferred simulator (default: first detected)
        
    Returns:
        List of CVDP items
    """
    # Choose simulator for harness
    sims = analysis.detected_simulators
    sim = prefer or (sims[0] if sims else Simulator.XCELIUM)

    items: List[CvdpItem] = []

    for idx, test in enumerate(analysis.tests, 1):
        # Minimal context: the original test and nearby files
        likely_files = [test.file_path.relative_to(analysis.repo_root)]
        
        # Add package file if present in same dir
        pkg_files = list(test.file_path.parent.glob("*_pkg.sv"))
        for p in pkg_files[:1]:  # Just one package file
            likely_files.append(p.relative_to(analysis.repo_root))

        ctx = _collect_context(analysis.repo_root, likely_files)

        # Harness commands per simulator
        if sim == Simulator.XCELIUM:
            run_cmd = "make -C /code/sim/cadence_sim run TEST=$TEST || exit 1"
            harness = harness_for_xcelium(run_cmd, f"dvsmith-{idx:04d}")
        elif sim == Simulator.QUESTA:
            run_cmd = "make -C /code/sim/questa_sim run TEST=$TEST || exit 1"
            harness = harness_for_questa(run_cmd, f"dvsmith-{idx:04d}")
        elif sim == Simulator.VCS:
            run_cmd = "make -C /code/sim/synopsys_sim run TEST=$TEST || exit 1"
            harness = harness_for_vcs(run_cmd, f"dvsmith-{idx:04d}")
        else:
            # Fallback
            run_cmd = "make -C /code/sim run TEST=$TEST || exit 1"
            harness = harness_for_xcelium(run_cmd, f"dvsmith-{idx:04d}")

        items.append(CvdpItem(
            id=f"dvsmith_agentic_{idx:04d}",
            categories=["cid005", "medium"],  # Can be refined based on test difficulty
            system_message=_system_message(),
            prompt=_prompt_for_test(test, analysis.repo_root),
            context=ctx,
            patch={},
            harness=harness,
        ))

    return items


def write_jsonl(items: List[CvdpItem], out_path: Path) -> None:
    """Write CVDP items to JSONL file.
    
    Args:
        items: List of CVDP items
        out_path: Output file path
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(item.to_json() + "\n")
