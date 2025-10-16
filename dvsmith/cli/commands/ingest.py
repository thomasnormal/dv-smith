
async def run_ingest(repo_url:str, name:Optional[str], workspace:Path):
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
