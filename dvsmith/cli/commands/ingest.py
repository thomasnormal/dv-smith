"""Ingest command - capture repository snapshot for terminal-bench generation."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ...core.ai_analyzer import AIRepoAnalyzer
from ...core.models import RepoAnalysis
from ..live_feed import with_live_agent_feed

console = Console()


def ingest_command(
    repo_url: str = typer.Argument(..., help="Repository URL or local path"),
    name: Optional[str] = typer.Option(None, help="Profile name (default: derived from repo)"),
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """Analyze a repository and store snapshot metadata."""

    async def run_ingest() -> None:
        profile_name = derive_name(repo_url, name)

        console.print(f"[cyan]Ingesting repository:[/] {repo_url}")
        console.print(f"[cyan]Profile name:[/] {profile_name}")

        repo_path = await ensure_repo_clone(repo_url, workspace / "clones", profile_name)

        analyzer = AIRepoAnalyzer(repo_root=repo_path)
        analysis: RepoAnalysis = await with_live_agent_feed(
            analyzer.analyze,
            console,
            title="Analyzing Repository",
        )

        if not analysis.git_remote and repo_url.startswith(("http://", "https://", "git@")):
            analysis.git_remote = repo_url
        if not analysis.git_commit:
            raw_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if raw_commit.returncode == 0:
                analysis.git_commit = raw_commit.stdout.strip()

        if not analysis.git_remote:
            console.print(
                "[yellow]⚠ Could not determine git remote. Docker scaffolds require a remote URL for ADD commands.[/]"
            )
        if not analysis.git_commit:
            console.print("[yellow]⚠ Could not determine git commit hash.[/]")

        report_analysis(analysis)

        profile_dir = workspace / "profiles" / profile_name
        profile_dir.mkdir(parents=True, exist_ok=True)

        analysis_path = profile_dir / "repo_analysis.json"
        analysis_dict = analysis.to_dict()
        analysis_dict["repo_root"] = str(repo_path)
        analysis_path.write_text(json.dumps(analysis_dict, indent=2))

        console.print(f"[green]✓ Analysis saved:[/] {analysis_path}")
        console.print("[green]✓ Ingest complete![/]")

    asyncio.run(run_ingest())


def derive_name(repo_url: str, explicit_name: Optional[str]) -> str:
    if explicit_name:
        return explicit_name
    if repo_url.startswith(("http://", "https://", "git@")):
        derived = repo_url.rstrip("/").split("/")[-1]
    else:
        derived = Path(repo_url).stem
    return derived.replace(".git", "").replace("-", "_")


async def ensure_repo_clone(repo_url: str, clones_dir: Path, name: str) -> Path:
    if repo_url.startswith(("http://", "https://", "git@")):
        clones_dir.mkdir(parents=True, exist_ok=True)
        repo_path = clones_dir / name
        if repo_path.exists():
            shutil.rmtree(repo_path)
        result = await asyncio.to_thread(
            subprocess.run,
            ["git", "clone", repo_url, str(repo_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr}")
        return repo_path

    repo_path = Path(repo_url).resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path not found: {repo_path}")
    return repo_path


def report_analysis(analysis: RepoAnalysis) -> None:
    table = Table(title="Repository Snapshot", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Commit", analysis.git_commit or "unknown")
    table.add_row("Remote", analysis.git_remote or "unknown")
    simulators = ", ".join(sim.value for sim in analysis.detected_simulators) or "none"
    table.add_row("Simulators", simulators)
    table.add_row("Covergroups", str(len(analysis.get_covergroups())))
    table.add_row("Assertion files", str(len(analysis.assertion_files)))
    table.add_row("Coverage files", str(len(analysis.coverage_files)))
    table.add_row("Tests", str(len(analysis.tests)))

    console.print(table)
