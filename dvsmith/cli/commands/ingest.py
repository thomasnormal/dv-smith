"""Ingest command - analyze repository and create profile."""

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ...config import Profile
from ...core.ai_analyzer import AIRepoAnalyzer
from ..live_feed import with_live_agent_feed


console = Console()


def ingest_command(
    repo_url: str = typer.Argument(..., help="Repository URL or local path"),
    name: Optional[str] = typer.Option(None, help="Gym name (default: derived from repo)"),
    workspace: Path = typer.Option(
        Path("./dvsmith_workspace"), help="Workspace directory"
    ),
):
    """Analyze a repository and generate a profile."""
    
    async def run_ingest():
        # Derive name from repo
        if name is None:
            if repo_url.startswith(("http://", "https://", "git@")):
                derived_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "").replace("-", "_")
            else:
                derived_name = Path(repo_url).stem.replace("-", "_")
        else:
            derived_name = name
        
        console.print(f"[cyan]Ingesting repository:[/] {repo_url}")
        console.print(f"[cyan]Gym name:[/] {derived_name}")
        
        # Clone if URL
        if repo_url.startswith(("http://", "https://", "git@")):
            clones_dir = workspace / "clones"
            clones_dir.mkdir(parents=True, exist_ok=True)
            
            repo_path = clones_dir / derived_name
            
            if repo_path.exists():
                console.print(f"[yellow]Removing existing clone:[/] {repo_path}")
                shutil.rmtree(repo_path)
            
            console.print(f"[cyan]Cloning to:[/] {repo_path}")
            result = subprocess.run(
                ["git", "clone", repo_url, str(repo_path)],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                console.print(f"[red]Clone failed:[/] {result.stderr}")
                raise typer.Exit(1)
        else:
            repo_path = Path(repo_url)
        
        # Run AI analysis with live agent feed
        analysis = await with_live_agent_feed(
            AIRepoAnalyzer(repo_root=repo_path).analyze,
            console,
            title="Analyzing Repository",
            show_progress=False
        )
        
        console.print("[green]✓ Analysis complete![/]")
        
        # Display results in a nice table
        table = Table(title="Analysis Results", show_header=True)
        table.add_column("Component", style="cyan")
        table.add_column("Count", style="green")
        
        table.add_row("Tests", str(len(analysis.tests)))
        table.add_row("Sequences", str(len(analysis.sequences)))
        covergroup_names = analysis.get_covergroups()
        table.add_row("Covergroups", str(len(covergroup_names)))
        build_system_value = analysis.build_system.value if analysis.build_system else "unknown"
        table.add_row("Build System", build_system_value)
        simulators_display = ", ".join(s.value for s in analysis.detected_simulators) or "none"
        table.add_row("Simulators", simulators_display)
        
        console.print(table)
        
        # Save profile
        profiles_dir = workspace / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        profile_path = profiles_dir / f"{derived_name}.yaml"
        
        # Create Profile with cached analysis path
        profile = Profile(
            name=derived_name,
            repo_url=str(repo_path),
            description=f"Profile for {derived_name}",
            simulators=[s.value for s in analysis.detected_simulators],
            paths={
                "root": ".",
                "tests": str(analysis.tests_dir.relative_to(repo_path)) if analysis.tests_dir else "tests",
                "sequences": str(analysis.sequences_dir.relative_to(repo_path)) if analysis.sequences_dir else None,
                "env": str(analysis.env_dir.relative_to(repo_path)) if analysis.env_dir else None,
            },
            build={},
            coverage={},
            grading={
                "smoke_tests": [analysis.tests[0].name] if analysis.tests else [],
                "weights": {
                    "functional_coverage": 0.6,
                    "code_coverage": 0.3,
                    "health": 0.1,
                },
            },
            metadata={
                "test_count": len(analysis.tests),
                "sequence_count": len(analysis.sequences),
                "covergroup_count": len(covergroup_names),
                "build_system": build_system_value,
                "covergroups": covergroup_names,
                "analysis": analysis.to_dict(),
            },
        )
        
        profile.to_yaml(profile_path)
        
        console.print(f"\n[green]✓ Profile saved:[/] {profile_path}")
        console.print("[green]✓ Ingest complete![/]")
    
    asyncio.run(run_ingest())
