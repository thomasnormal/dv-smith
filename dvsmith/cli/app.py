"""Typer-based CLI for dv-smith with Rich output."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table
from rich.traceback import install

# Install rich traceback handler for better error display
install(show_locals=False)

# Disable Claude Code IDE integration hooks FIRST
if os.getenv("CLAUDECODE") or os.getenv("AGENT") == "amp":
    os.environ.pop("CLAUDECODE", None)
    os.environ["CLAUDE_NO_IDE"] = "1"

from dotenv import load_dotenv

load_dotenv()

from ..core.ai_analyzer import AIRepoAnalyzer
from ..config import Profile
from .live_feed import with_live_agent_feed
from .agent_runner import run_agent_with_feed

# Read version from pyproject.toml
try:
    import tomllib
except ImportError:
    import tomli as tomllib

__version__ = "0.2.0"

def get_version() -> str:
    """Get version from pyproject.toml."""
    try:
        pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", __version__)
    except Exception:
        pass
    return __version__

app = typer.Typer(
    name="dvsmith",
    help="Convert SystemVerilog/UVM testbenches into DV gyms",
    add_completion=False,
)
console = Console()

# CVDP sub-app
cvdp_app = typer.Typer(help="CVDP-compatible operations")


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"dvsmith version {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """DV-Smith: UVM verification gym builder."""
    pass


@app.command()
def ingest(
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
            import subprocess
            
            clones_dir = workspace / "clones"
            clones_dir.mkdir(parents=True, exist_ok=True)
            
            repo_path = clones_dir / derived_name
            
            if repo_path.exists():
                console.print(f"[yellow]Removing existing clone:[/] {repo_path}")
                import shutil
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
        analyzer = AIRepoAnalyzer(repo_root=repo_path)
        analysis = await with_live_agent_feed(
            analyzer.analyze,
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
        table.add_row("Covergroups", str(len(analysis.covergroups)))
        table.add_row("Build System", str(analysis.build_system.value))
        table.add_row("Simulators", ", ".join(s.value for s in analysis.detected_simulators))
        
        console.print(table)
        
        # Save profile
        profiles_dir = workspace / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        
        profile_path = profiles_dir / f"{derived_name}.yaml"
        
        # Create Profile object with analysis cache
        from ..core.models import RepoAnalysis
        
        # Convert analysis to dict for caching
        analysis_cache = {
            "tests": [
                {
                    "name": t.name,
                    "file_path": str(t.file_path.relative_to(repo_path)),
                    "base_class": t.base_class,
                    "description": t.description,
                }
                for t in analysis.tests
            ],
            "sequences": [
                {
                    "name": s.name,
                    "file_path": str(s.file_path.relative_to(repo_path)),
                    "base_class": s.base_class,
                }
                for s in analysis.sequences
            ],
            "covergroups": analysis.covergroups,
            "build_system": analysis.build_system.value,
            "detected_simulators": [s.value for s in analysis.detected_simulators],
            "repo_root": str(repo_path),
            "tests_dir": str(analysis.tests_dir.relative_to(repo_path)) if analysis.tests_dir else None,
            "sequences_dir": str(analysis.sequences_dir.relative_to(repo_path)) if analysis.sequences_dir else None,
            "env_dir": str(analysis.env_dir.relative_to(repo_path)) if analysis.env_dir else None,
            "agents_dir": str(analysis.agents_dir.relative_to(repo_path)) if analysis.agents_dir else None,
        }
        
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
                "covergroup_count": len(analysis.covergroups),
                "build_system": analysis.build_system.value,
                "covergroups": analysis.covergroups,
            },
            analysis_cache=analysis_cache,
        )
        
        profile.to_yaml(profile_path)
        
        console.print(f"\n[green]✓ Profile saved:[/] {profile_path}")
        console.print("[green]✓ Ingest complete![/]")
    
    asyncio.run(run_ingest())


@app.command()
def build(
    name: str = typer.Argument(..., help="Gym name"),
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
    max_tasks: Optional[int] = typer.Option(None, "--max-tasks", "-n", help="Maximum number of tasks to generate"),
    skip_verification: bool = typer.Option(False, "--skip-verify", help="Skip verification step"),
):
    """Build a gym from an analyzed profile."""
    
    async def run_build():
        from ..core.gym_cleaner import GymCleaner
        from ..core.task_generator import TaskGenerator
        from ..core.models import TaskCategory, RepoAnalysis
        
        console.print(f"[cyan]Building gym:[/] {name}")
        
        # Load profile
        profile_path = workspace / "profiles" / f"{name}.yaml"
        if not profile_path.exists():
            console.print(f"[red]✗ Profile not found:[/] {profile_path}")
            raise typer.Exit(1)
        
        profile = Profile.from_yaml(profile_path)
        
        # Load cached analysis
        if not profile.analysis_cache:
            console.print("[red]✗ No cached analysis found. Run 'ingest' first.[/]")
            raise typer.Exit(1)
        
        repo_path = Path(profile.repo_url)
        console.print(f"[cyan]Repository:[/] {repo_path}")
        
        # Reconstruct analysis from cache
        analysis = RepoAnalysis.from_dict(profile.analysis_cache, repo_root=repo_path)
        
        # Setup gym structure
        gym_dir = workspace / "gyms" / name
        gym_dir.mkdir(parents=True, exist_ok=True)
        tasks_dir = gym_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        
        console.print(f"[cyan]Gym directory:[/] {gym_dir}")
        
        # Copy repository structure to gym
        with console.status("[cyan]Copying repository structure..."):
            import shutil
            
            # Copy source directories
            for src_dir in ['src', 'rtl', 'tb', 'sim']:
                src_path = repo_path / src_dir
                if src_path.exists():
                    dest_path = gym_dir / src_dir
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(src_path, dest_path, symlinks=False, ignore=shutil.ignore_patterns('*.log', '*.vcd', 'work', '*.ucdb'))
            
            # Copy build files
            for build_file in ['Makefile', 'makefile', 'CMakeLists.txt']:
                build_path = repo_path / build_file
                if build_path.exists():
                    shutil.copy2(build_path, gym_dir / build_file)
        
        console.print(f"[green]✓ Copied repository structure[/]")
        
        # Prepare for task generation and cleaning
        smoke_tests = profile.grading.smoke_tests
        
        # Clean test directory using Claude (keep infrastructure, remove task tests)
        from pydantic import BaseModel, Field
        
        class CleanupPlan(BaseModel):
            """Plan for cleaning test directory."""
            keep: list[str] = Field(default_factory=list, description="Files to keep (infrastructure)")
            remove: list[str] = Field(default_factory=list, description="Files to remove (task tests)")
            
        # Get list of tests that will become tasks
        task_test_names = [t.name for t in analysis.tests if t.name not in smoke_tests and "base" not in t.name.lower()]
        if max_tasks:
            task_test_names = task_test_names[:max_tasks]
        
        console.print(f"[cyan]Analyzing which files to clean ({len(task_test_names)} task tests)...[/]")
        
        # Use Claude to decide what to keep/remove
        cleanup_prompt = f"""You are helping prepare a UVM verification gym by cleaning the test directory.

Repository: {repo_path}
Test directory: {analysis.tests_dir}

Tests that will become TASKS (should be REMOVED from gym):
{chr(10).join(f"  - {name}" for name in task_test_names[:20])}

Smoke tests (must be KEPT):
{chr(10).join(f"  - {name}" for name in smoke_tests)}

Your job:
1. Identify which test files should be REMOVED (the task tests above)
2. Identify which files should be KEPT (base tests, packages, infrastructure)

Return CleanupPlan with:
- keep: List of filenames to preserve (base_test.sv, *_pkg.sv, etc.)
- remove: List of filenames to delete (task test files)

Work from the test directory: {gym_dir / analysis.tests_dir.relative_to(repo_path) if analysis.tests_dir else gym_dir}
"""
        
        # Call Claude directly (not via with_live_agent_feed since it's quick)
        with console.status("[cyan]Planning cleanup with Claude..."):
            from ..core.ai_structured import query_with_pydantic_response
            cleanup_plan = await query_with_pydantic_response(
                prompt=cleanup_prompt,
                response_model=CleanupPlan,
                system_prompt="You are an expert at UVM testbench structure.",
                cwd=str(gym_dir)
            )
        
        # Execute cleanup
        test_dir_in_gym = gym_dir / analysis.tests_dir.relative_to(repo_path) if analysis.tests_dir else None
        if test_dir_in_gym and test_dir_in_gym.exists():
            removed_count = 0
            for filename in cleanup_plan.remove:
                test_file = test_dir_in_gym / filename
                if test_file.exists():
                    test_file.unlink()
                    removed_count += 1
            console.print(f"[green]✓ Removed {removed_count} task test files, kept {len(cleanup_plan.keep)} infrastructure files[/]")
        
        # Generate tasks (with optional limit)
        task_gen = TaskGenerator(analysis, profile.to_dict())
        
        # Limit number of tasks if specified
        if max_tasks:
            # Temporarily reduce test list
            original_tests = analysis.tests
            analysis.tests = [t for t in original_tests if t.name not in smoke_tests][:max_tasks]
        
        # Use live feed for task generation (shows AI working on each task)
        task_count_msg = f"{max_tasks} tasks" if max_tasks else f"{len([t for t in analysis.tests if t.name not in smoke_tests])} tasks"
        console.print(f"[cyan]Generating {task_count_msg}...[/]")
        
        tasks = await with_live_agent_feed(
            task_gen.generate_tasks_async,
            console,
            title=f"Generating Tasks (0/{len([t for t in analysis.tests if t.name not in smoke_tests])})",
            max_messages=3,
            output_dir=tasks_dir,
            smoke_tests=smoke_tests
        )
        
        # Restore original tests
        if max_tasks:
            analysis.tests = original_tests
        
        console.print(f"[green]✓ Generated {len(tasks)} tasks[/]")
        
        # Create backups
        backups_dir = gym_dir / "backups" / "original_tests"
        backups_dir.mkdir(parents=True, exist_ok=True)
        
        with console.status(f"[cyan]Backing up {len(analysis.tests)} test files..."):
            for test in analysis.tests:
                if test.file_path.exists():
                    dest = backups_dir / test.file_path.name
                    import shutil
                    shutil.copy2(test.file_path, dest)
        
        console.print(f"[green]✓ Backed up test files to:[/] {backups_dir}")
        console.print(f"[green]✓ Build complete![/]")
        
        # Show summary table
        table = Table(title="Gym Summary")
        table.add_column("Component", style="cyan")
        table.add_column("Count", style="green", justify="right")
        
        table.add_row("Tasks Generated", str(len(tasks)))
        table.add_row("Tests Backed Up", str(len(analysis.tests)))
        table.add_row("Sequences", str(len(analysis.sequences)))
        table.add_row("Gym Location", str(gym_dir))
        
        console.print(table)
    
    asyncio.run(run_build())


@app.command()
def validate_profile(
    profile_path: Path = typer.Argument(..., help="Path to profile YAML"),
):
    """Validate a profile file."""
    try:
        profile = Profile.from_yaml(profile_path)
        
        console.print(Panel.fit(
            f"[green]✓ Profile is valid![/]\n\n"
            f"Name: {profile.name}\n"
            f"Tests: {profile.metadata.test_count}\n"
            f"Simulators: {', '.join(profile.simulators)}",
            title="Profile Validation",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]✗ Profile validation failed:[/] {e}")
        raise typer.Exit(1)


@app.command()
def list_profiles(
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """List all available profiles."""
    profiles_dir = workspace / "profiles"
    
    if not profiles_dir.exists():
        console.print("[yellow]No profiles found[/]")
        return
    
    profiles = list(profiles_dir.glob("*.yaml"))
    
    if not profiles:
        console.print("[yellow]No profiles found[/]")
        return
    
    table = Table(title=f"Available Profiles ({len(profiles)})")
    table.add_column("Name", style="cyan")
    table.add_column("Tests", style="green")
    table.add_column("Simulators", style="yellow")
    
    for prof_file in sorted(profiles):
        try:
            prof = Profile.from_yaml(prof_file)
            table.add_row(
                prof.name,
                str(prof.metadata.test_count),
                ", ".join(prof.simulators[:3])
            )
        except Exception as e:
            table.add_row(prof_file.stem, "[red]Invalid[/]", str(e)[:30])
    
    console.print(table)


@app.command()
def info(
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """Show workspace statistics and information."""
    
    # Gather stats
    profiles_dir = workspace / "profiles"
    gyms_dir = workspace / "gyms"
    clones_dir = workspace / "clones"
    
    profile_count = len(list(profiles_dir.glob("*.yaml"))) if profiles_dir.exists() else 0
    gym_count = len(list(gyms_dir.iterdir())) if gyms_dir.exists() else 0
    clone_count = len(list(clones_dir.iterdir())) if clones_dir.exists() else 0
    
    # Calculate total tests
    total_tests = 0
    if profiles_dir.exists():
        for prof_file in profiles_dir.glob("*.yaml"):
            try:
                prof = Profile.from_yaml(prof_file)
                total_tests += prof.metadata.test_count
            except:
                pass
    
    # Display info panel
    info_text = f"""[cyan]Workspace:[/] {workspace}

[bold]Profiles:[/] {profile_count}
[bold]Gyms:[/] {gym_count}
[bold]Clones:[/] {clone_count}
[bold]Total Tests:[/] {total_tests}

[bold]AI Logs:[/] ~/.dvsmith/ai_calls.jsonl
[bold]Version:[/] {__version__}"""
    
    console.print(Panel(info_text, title="DV-Smith Workspace Info", border_style="cyan"))
    
    # Show profile summary if any exist
    if profile_count > 0:
        table = Table(title="Profile Summary")
        table.add_column("Profile", style="cyan")
        table.add_column("Tests", style="green", justify="right")
        table.add_column("Covergroups", style="yellow", justify="right")
        
        for prof_file in sorted(profiles_dir.glob("*.yaml"))[:10]:
            try:
                prof = Profile.from_yaml(prof_file)
                table.add_row(
                    prof.name,
                    str(prof.metadata.test_count),
                    str(prof.metadata.covergroup_count)
                )
            except:
                pass
        
        console.print(table)


@cvdp_app.command("export")
def cvdp_export(
    repo: Path = typer.Argument(..., help="Repository path"),
    out: Path = typer.Option(Path("dvsmith_cvdp.jsonl"), "--out", "-o", help="Output JSONL file"),
    prefer_sim: Optional[str] = typer.Option(None, "--sim", help="Preferred simulator (questa|xcelium|vcs)"),
):
    """Export repository analysis to CVDP format."""
    
    async def run_export():
        from ..cvdp.exporter import build_cvdp_items, write_jsonl
        from ..core.models import Simulator
        
        console.print(f"[cyan]Analyzing repository:[/] {repo}")
        
        # Use live agent feed utility
        analyzer = AIRepoAnalyzer(repo_root=repo)
        analysis = await with_live_agent_feed(
            analyzer.analyze,
            console,
            title="CVDP Analysis",
            show_progress=False
        )
        
        # Convert to CVDP items
        sim = Simulator(prefer_sim) if prefer_sim else None
        items = build_cvdp_items(analysis, prefer=sim)
        
        # Write JSONL
        write_jsonl(items, out)
        
        console.print(f"\n[green]✓ Exported {len(items)} CVDP items to:[/] {out}")
        console.print(f"[cyan]Tests:[/] {len(analysis.tests)}")
        console.print(f"[cyan]Simulator:[/] {prefer_sim or 'auto-detected'}")
    
    asyncio.run(run_export())


@app.command()
def run(
    agent: Path = typer.Argument(..., help="Path to agent script"),
    task: Path = typer.Argument(..., help="Path to task markdown file"),
    output: Path = typer.Argument(..., help="Output directory for solution"),
):
    """Run an agent on a task with live feed display."""
    
    async def run_agent():
        if not agent.exists():
            console.print(f"[red]✗ Agent script not found:[/] {agent}")
            raise typer.Exit(1)
        
        if not task.exists():
            console.print(f"[red]✗ Task file not found:[/] {task}")
            raise typer.Exit(1)
        
        exit_code = await run_agent_with_feed(agent, task, output, console)
        
        if exit_code != 0:
            raise typer.Exit(exit_code)
    
    asyncio.run(run_agent())


@app.command()
def eval(
    task: Path = typer.Option(..., "--task", help="Path to task markdown file"),
    patch: Path = typer.Option(..., "--patch", help="Path to solution patch file"),
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
):
    """Evaluate a solution patch against a task (placeholder)."""
    
    console.print(f"[cyan]Evaluating solution:[/]")
    console.print(f"  Task: {task}")
    console.print(f"  Patch: {patch}")
    console.print()
    
    if not task.exists():
        console.print(f"[red]✗ Task not found:[/] {task}")
        raise typer.Exit(1)
    
    if not patch.exists():
        console.print(f"[red]✗ Patch not found:[/] {patch}")
        raise typer.Exit(1)
    
    # Check patch file size
    patch_size = patch.stat().st_size
    if patch_size == 0:
        console.print(f"[yellow]⚠ Warning: Patch file is empty (0 bytes)[/]")
        console.print(f"[yellow]  This usually means the agent didn't generate a proper patch.[/]")
        console.print()
        
        # Check for .sv files in same directory
        sv_files = list(patch.parent.glob("*.sv"))
        if sv_files:
            console.print(f"[cyan]Found {len(sv_files)} .sv file(s) in solution directory:[/]")
            for sv in sv_files:
                console.print(f"  • {sv.name}")
            console.print()
            console.print("[yellow]Note: Full eval implementation coming in future version.[/]")
            console.print("[yellow]For now, use: dvsmith-old eval --task ... --patch ...[/]")
        raise typer.Exit(1)
    
    console.print(f"[green]✓ Patch file size: {patch_size} bytes[/]")
    console.print()
    console.print("[yellow]Note: Full eval implementation coming in future version.[/]")
    console.print("[yellow]For now, use: dvsmith-old eval --task ... --patch ...[/]")


# Add cvdp sub-app to main app
app.add_typer(cvdp_app, name="cvdp")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
