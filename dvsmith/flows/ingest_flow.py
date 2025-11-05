"""Prefect-based orchestration for repository ingestion."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from prefect import flow, get_run_logger
from prefect.exceptions import MissingContextError
from rich.console import Console

from ..core.ai_analyzer import AIRepoAnalyzer
from ..core.models import RepoAnalysis


@flow(name="Ingest Repository", validate_parameters=False)
async def ingest_repository(
    repo_url: str,
    profile_name: str,
    workspace: Path,
    console: Console,
) -> dict:
    """Main Prefect flow for ingesting a repository.

    Args:
        repo_url: Repository URL or local path
        profile_name: Profile name for the ingested repository
        workspace: Workspace directory
        console: Rich console for output

    Returns:
        Dictionary containing the analysis data and metadata
    """
    try:
        logger = get_run_logger()
    except MissingContextError:
        logger = logging.getLogger("dvsmith.ingest_flow")

    logger.debug(f"Starting repository ingestion: {repo_url}")
    logger.debug(f"Profile name: {profile_name}")

    # Clone or validate repository
    repo_path = await ensure_repo_clone(repo_url, workspace / "clones", profile_name)
    logger.debug(f"Repository path: {repo_path}")

    # Run AI analysis with status updates
    console.print("[cyan]Analyzing repository...[/cyan]\n")

    def status_callback(msg: str):
        console.print(f"  [dim]{msg}[/dim]")

    analyzer = AIRepoAnalyzer(repo_root=repo_path)
    analysis: RepoAnalysis = await analyzer.analyze(status_cb=status_callback)
    logger.debug("Analysis complete")

    # Enrich with git metadata
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

    # Warn about missing metadata
    if not analysis.git_remote:
        logger.warning("Could not determine git remote. Docker scaffolds require a remote URL.")
    if not analysis.git_commit:
        logger.warning("Could not determine git commit hash.")

    # Save analysis to profile directory
    profile_dir = workspace / "profiles" / profile_name
    profile_dir.mkdir(parents=True, exist_ok=True)

    analysis_path = profile_dir / "repo_analysis.json"
    analysis_dict = analysis.to_dict()
    analysis_dict["repo_root"] = str(repo_path)
    analysis_path.write_text(json.dumps(analysis_dict, indent=2))
    logger.debug(f"Analysis saved to: {analysis_path}")

    return {
        "profile_name": profile_name,
        "profile_dir": str(profile_dir),
        "analysis_path": str(analysis_path),
        "analysis": analysis_dict,
    }


async def ensure_repo_clone(repo_url: str, clones_dir: Path, name: str) -> Path:
    """Clone repository if needed or validate local path.

    Args:
        repo_url: Repository URL or local path
        clones_dir: Directory for clones
        name: Profile name (used for clone directory name)

    Returns:
        Path to repository

    Raises:
        RuntimeError: If git clone fails
        FileNotFoundError: If local repository path not found
    """
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


__all__ = ["ingest_repository", "ensure_repo_clone"]
