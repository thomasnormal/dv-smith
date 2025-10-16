"""Build command - create gym from profile."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from pydantic import BaseModel, Field

from ...core.task_generator import TaskGenerator
from ...core.models import RepoAnalysis
from ...config import Profile
from ..live_feed import with_live_agent_feed


console = Console()


def build_command(
    name: str = typer.Argument(..., help="Gym name"),
    workspace: Path = typer.Option(Path("./dvsmith_workspace"), help="Workspace directory"),
    max_tasks: Optional[int] = typer.Option(None, "--max-tasks", "-n", help="Maximum number of tasks to generate"),
    skip_verification: bool = typer.Option(False, "--skip-verify", help="Skip verification step"),
):
    """Build a gym from an analyzed profile."""
    
    async def run_build():
        from ...core.ai_structured import query_with_pydantic_response
        
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
        
        # Clean test directory using Claude
        class CleanupPlan(BaseModel):
            """Plan for cleaning test directory."""
            keep: list[str] = Field(default_factory=list)
            remove: list[str] = Field(default_factory=list)
            
        # Get list of tests that will become tasks
        task_test_names = [t.name for t in analysis.tests if t.name not in smoke_tests and "base" not in t.name.lower()]
        if max_tasks:
            task_test_names = task_test_names[:max_tasks]
        
        console.print(f"[cyan]Analyzing which files to clean ({len(task_test_names)} task tests)...[/]")
        
        # Use Claude to decide what to keep/remove
        cleanup_prompt = f"""You are helping prepare a UVM verification gym by cleaning the test directory.

Tests that will become TASKS (should be REMOVED from gym):
{chr(10).join(f"  - {name}" for name in task_test_names)}

Smoke tests (must be KEPT):
{chr(10).join(f"  - {name}" for name in smoke_tests)}

Your job:
1. Identify which test files should be REMOVED (the task tests above)
2. Identify which files should be KEPT (base tests, packages, infrastructure)

Return CleanupPlan with:
- keep: List of filenames to preserve
- remove: List of filenames to delete

Explore files and decide what to keep vs remove.
"""
        
        # Call Claude for cleanup plan
        with console.status("[cyan]Planning cleanup with Claude..."):
            cleanup_plan = await query_with_pydantic_response(
                prompt=cleanup_prompt,
                response_model=CleanupPlan,
                system_prompt="You are an expert at UVM testbench structure.",
                cwd=str(gym_dir)
            )
        
        # Execute cleanup
        if analysis.tests_dir:
            if analysis.tests_dir.is_absolute():
                test_dir_rel = analysis.tests_dir.relative_to(repo_path)
            else:
                test_dir_rel = analysis.tests_dir
            test_dir_in_gym = gym_dir / test_dir_rel
        else:
            test_dir_in_gym = None
            
        if test_dir_in_gym and test_dir_in_gym.exists():
            removed_count = 0
            for filename in cleanup_plan.remove:
                test_file = test_dir_in_gym / filename
                if test_file.exists():
                    test_file.unlink()
                    removed_count += 1
            console.print(f"[green]✓ Removed {removed_count} task test files, kept {len(cleanup_plan.keep)} infrastructure files[/]")
        
        # Generate tasks
        task_gen = TaskGenerator(analysis, profile.to_dict())
        
        if max_tasks:
            original_tests = analysis.tests
            analysis.tests = [t for t in original_tests if t.name not in smoke_tests][:max_tasks]
        
        task_count_msg = f"{max_tasks} tasks" if max_tasks else f"{len([t for t in analysis.tests if t.name not in smoke_tests])} tasks"
        console.print(f"[cyan]Generating {task_count_msg}...[/]")
        
        tasks = await with_live_agent_feed(
            task_gen.generate_tasks_async,
            console,
            title=f"Generating Tasks",
            max_messages=3,
            output_dir=tasks_dir,
            smoke_tests=smoke_tests
        )
        
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
