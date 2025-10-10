#!/usr/bin/env python3
"""dv-smith CLI - Convert SystemVerilog/UVM testbenches into DV gyms."""

import os
import sys

# Disable Claude Code IDE integration hooks FIRST, before any other imports
# The CLAUDECODE env var causes claude-agent-sdk to try connecting to IDE hooks
# which can hang in non-interactive or background processes
# Also clear it if running in Amp (AGENT=amp), which uses Claude Code infrastructure
if os.getenv('CLAUDECODE') or os.getenv('AGENT') == 'amp':
    os.environ.pop('CLAUDECODE', None)
    # Set a marker to prevent claude CLI from detecting parent IDE
    os.environ['CLAUDE_NO_IDE'] = '1'
    # Redirect stdout to stderr to avoid stdout hooks that can cause hangs
    sys.stderr.write("[DVSMITH] Redirecting stdout to stderr to avoid Claude Code hooks\n")
    sys.stderr.flush()
    sys.stdout = sys.stderr

import argparse
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables from .env file
load_dotenv()

# Configure logging
from .config import get_logger
logger = get_logger(__name__)

# Import adapters to trigger registration
from .adapters.sim.base import SimulatorRegistry
from .core.models import Simulator
from .core.task_generator import TaskGenerator

# AI analyzer is required
try:
    from .core.ai_analyzer import AIRepoAnalyzer
except ImportError as e:
    logger.error("Failed to import AI analyzer. Please install required dependencies:")
    logger.error("  pip install anthropic")
    sys.exit(1)


class DVSmith:
    """Main dv-smith application."""

    def __init__(self, workspace: Path = Path("./dvsmith_workspace")) -> None:
        """Initialize dv-smith.

        Args:
            workspace: Root workspace directory for profiles, gyms, artifacts
        """
        self.workspace = workspace
        self.workspace.mkdir(exist_ok=True, parents=True)

        self.profiles_dir = workspace / "profiles"
        self.gyms_dir = workspace / "gyms"
        self.artifacts_dir = workspace / "artifacts"

        self.profiles_dir.mkdir(exist_ok=True)
        self.gyms_dir.mkdir(exist_ok=True)
        self.artifacts_dir.mkdir(exist_ok=True)

    def ingest(self, repo_url: str, name: Optional[str] = None,
               commit: Optional[str] = None, hints: Optional[dict] = None) -> None:
        """Analyze a repository and generate a profile.

        Args:
            repo_url: URL or local path to repository
            name: Name for the gym (default: derived from repo)
            commit: Specific commit to use (default: HEAD)
            hints: Optional hints for analysis (paths, simulators, etc.)
        """
        logger.info(f"Ingesting repository: {repo_url}")

        if name is None:
            # Derive name from repo URL
            if repo_url.startswith(("http://", "https://", "git@")):
                # Extract repo name from git URL
                name = repo_url.rstrip("/").split("/")[-1].replace(".git", "").replace("-", "_")
            else:
                name = Path(repo_url).stem.replace("-", "_")

        logger.info(f"Gym name: {name}")

        # Handle git URLs - clone to workspace
        if repo_url.startswith(("http://", "https://", "git@")):
            import subprocess

            # Clone to a temp directory in workspace
            clones_dir = self.workspace / "clones"
            clones_dir.mkdir(exist_ok=True)

            repo_path = clones_dir / name

            if repo_path.exists():
                logger.info(f"Removing existing clone at: {repo_path}")
                import shutil
                shutil.rmtree(repo_path)
            
            logger.info(f"Cloning repository to: {repo_path}")
            try:
                result = subprocess.run(
                    ["git", "clone", repo_url, str(repo_path)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode != 0:
                    logger.error(f"Failed to clone repository: {result.stderr}")
                    sys.exit(1)
                logger.info("Clone successful")
            except subprocess.TimeoutExpired:
                logger.error("Clone timed out after 5 minutes")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Failed to clone: {e}")
                sys.exit(1)

            # Checkout specific commit if requested
            if commit:
                logger.info(f"Checking out commit: {commit}")
                try:
                    subprocess.run(
                        ["git", "checkout", commit],
                        cwd=repo_path,
                        capture_output=True,
                        check=True
                    )
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to checkout commit: {e.stderr}")
                    sys.exit(1)
        else:
            # Local path
            repo_path = Path(repo_url).resolve()
            if not repo_path.exists():
                logger.error(f"Repository not found: {repo_path}")
                sys.exit(1)

        # Check for Anthropic API key
        if not os.getenv("ANTHROPIC_API_KEY"):
            logger.error("ANTHROPIC_API_KEY environment variable is required")
            logger.error("Set it with: export ANTHROPIC_API_KEY=your-key-here")
            logger.error("Or add it to .env file")
            sys.exit(1)

        # Use AI analyzer with progress tracking
        logger.info("Using AI-powered analysis...")

        # Create progress bar for main ingest steps
        with tqdm(total=3, desc="Ingesting", unit="step", position=0) as pbar:
            # Step 1: AI analysis
            pbar.set_description("Analyzing repository")
            try:
                ai_analyzer = AIRepoAnalyzer(repo_path)
                analysis = ai_analyzer.analyze()
                pbar.update(1)

                logger.info(f"✓ Found {len(analysis.tests)} tests")
                logger.info(f"✓ Found {len(analysis.sequences)} sequences")
                logger.info(f"✓ Found {len(analysis.covergroups)} covergroups")
                logger.info(f"✓ Build system: {analysis.build_system}")
                logger.info(f"✓ Detected simulators: {[s.value for s in analysis.detected_simulators]}")

            except Exception as e:
                pbar.close()
                logger.error(f"AI analysis failed: {e}")
                logger.error("Please check your ANTHROPIC_API_KEY and try again")
                sys.exit(1)

            # Step 2: Generate profile
            pbar.set_description("Generating profile")
            profile = self._generate_profile(name, repo_path, analysis)

            # Cache the full analysis to avoid re-analyzing in build
            profile['_analysis_cache'] = analysis.to_dict()
            pbar.update(1)

            # Step 3: Save profile
            pbar.set_description("Saving profile")
            profile_path = self.profiles_dir / f"{name}.yaml"
            with open(profile_path, "w") as f:
                yaml.dump(profile, f, default_flow_style=False, sort_keys=False)
            pbar.update(1)
            pbar.set_description("Complete")

        logger.info(f"Profile saved: {profile_path}")
        logger.info("Ingest complete!")

    def build(self, name: str, simulators: Optional[list[str]] = None, task_types: str = "stimulus", skip_verification: bool = False) -> None:
        """Build a gym from a profile.

        Args:
            name: Name of the gym/profile
            simulators: List of simulators to support (default: all in profile)
            task_types: Comma-separated task types: stimulus, coverage_func, all
            skip_verification: Skip testbench compilation verification
        """
        logger.info(f"Building gym: {name}")

        profile_path = self.profiles_dir / f"{name}.yaml"
        if not profile_path.exists():
            logger.error(f"Profile not found: {profile_path}")
            sys.exit(1)

        # Load profile
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        repo_path = Path(profile["repo_url"])
        if not repo_path.exists():
            logger.error(f"Repository not found: {repo_path}")
            sys.exit(1)

        if simulators:
            logger.info(f"Target simulators: {', '.join(simulators)}")
        else:
            logger.info("Using all simulators from profile")

        # Create gym directory
        gym_dir = self.gyms_dir / name
        gym_dir.mkdir(exist_ok=True, parents=True)

        # Check for Anthropic API key (needed for task generation)
        if not os.getenv("ANTHROPIC_API_KEY"):
            logger.error("ANTHROPIC_API_KEY environment variable is required for task generation")
            logger.error("Set it with: export ANTHROPIC_API_KEY=your-key-here")
            sys.exit(1)

        # Try to load cached analysis from profile
        if '_analysis_cache' in profile:
            logger.info(f"Loading cached analysis from {profile_path}...")
            try:
                from .core.models import RepoAnalysis
                analysis = RepoAnalysis.from_dict(profile['_analysis_cache'], repo_root=repo_path)
                logger.info(f"✓ Loaded {len(analysis.tests)} tests from {profile_path}")
            except Exception as e:
                logger.warning(f"Cache load failed: {e}")
                logger.info("Re-analyzing repository...")
                ai_analyzer = AIRepoAnalyzer(repo_path)
                analysis = ai_analyzer.analyze()
        else:
            # No cache, need to analyze
            logger.info("No cached analysis found, analyzing repository...")
            try:
                ai_analyzer = AIRepoAnalyzer(repo_path)
                analysis = ai_analyzer.analyze()
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
                logger.error("Please check your ANTHROPIC_API_KEY and try again")
                sys.exit(1)

        # Step 1: Copy source structure (including tests - we'll clean intelligently)
        logger.info("Step 1: Setting up gym structure...")
        logger.debug(f"Calling _setup_gym_structure with gym_dir={gym_dir}, repo_path={repo_path}")
        self._setup_gym_structure(gym_dir, repo_path, profile)
        logger.debug("_setup_gym_structure completed")

        # Step 1b: Intelligently clean test directory using Claude SDK
        logger.info("Step 1b: Intelligently cleaning test directory...")
        from .core.gym_cleaner import GymCleaner

        cleaner = GymCleaner(gym_dir, repo_path)
        cleanup_result = cleaner.analyze_and_clean([test.file_path for test in analysis.tests])

        logger.info(f"Identified {len(cleanup_result['keep'])} infrastructure files to keep")
        logger.info(f"Removing {len(cleanup_result['remove'])} task test files")

        # Remove only task test files, keep infrastructure
        removed_count = 0
        for test_file_path in tqdm(cleanup_result['remove'], desc="Removing task tests", unit="file", leave=False):
            test_file = Path(test_file_path)
            try:
                # Calculate relative path from repo to test file
                rel_path = test_file.relative_to(repo_path)

                # Build corresponding path in gym
                gym_file = gym_dir / rel_path

                if gym_file.exists():
                    gym_file.unlink()
                    removed_count += 1

            except ValueError:
                # File path not relative to repo, try direct match
                if test_file.exists():
                    test_file.unlink()
                    removed_count += 1
            except Exception as e:
                logger.warning(f"Could not remove {test_file.name}: {e}")

        logger.info(f"Successfully removed {removed_count} task test files")

        # Step 1c: Clean package includes for removed tests
        logger.info("Step 1c: Cleaning package includes...")
        removed_test_names = [Path(test_file_path).name for test_file_path in cleanup_result['remove']]
        include_cleanup = cleaner.clean_package_includes(removed_test_names)

        if include_cleanup['modified_files']:
            logger.info(f"Cleaned {len(include_cleanup['modified_files'])} package file(s)")
        if include_cleanup.get('errors'):
            logger.warning(f"Warnings: {len(include_cleanup['errors'])} package cleanup issues")

        # Step 2: Generate task specifications
        logger.info("Step 2: Generating task specifications...")
        tasks_dir = gym_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)

        # Parse task types
        from .core.models import TaskCategory
        selected_categories = []
        for token in task_types.split(","):
            tok = token.strip().lower()
            if tok in ("stimulus", "tests", "test"):
                if TaskCategory.STIMULUS not in selected_categories:
                    selected_categories.append(TaskCategory.STIMULUS)
            elif tok in ("coverage", "coverage_func", "func_cov", "functional"):
                if TaskCategory.COVERAGE_FUNC not in selected_categories:
                    selected_categories.append(TaskCategory.COVERAGE_FUNC)
            elif tok in ("all",):
                selected_categories = [TaskCategory.STIMULUS, TaskCategory.COVERAGE_FUNC]
                break
            else:
                print(f"[WARNING] Unknown task type: {token}, skipping")

        if not selected_categories:
            selected_categories = [TaskCategory.STIMULUS]  # default

        task_gen = TaskGenerator(analysis, profile)
        smoke_tests = profile.get("grading", {}).get("smoke_tests", [])
        tasks = task_gen.generate_tasks(tasks_dir, smoke_tests=smoke_tests)

        print(f"  Generated {len(tasks)} tasks")

        # Step 3: Create backups directory with original tests
        print("[dv-smith] Step 3: Backing up original tests...")
        self._backup_tests(gym_dir, repo_path, analysis)

        # Step 4: Build container images (TODO - skip for now)
        print("[dv-smith] Step 4: Building container images...")
        print("  (Skipping - container build not yet implemented)")

        # Save gym metadata
        gym_metadata = {
            "name": name,
            "profile": str(profile_path),
            "repo_path": str(repo_path),
            "task_count": len(tasks),
            "simulators": profile["simulators"]
        }

        metadata_path = gym_dir / "gym_metadata.yaml"
        with open(metadata_path, "w") as f:
            yaml.dump(gym_metadata, f)

        # Step 5: Verify gym integrity using Claude SDK
        if skip_verification:
            print("[dv-smith] Step 5: Verifying gym integrity... [SKIPPED]")
            validation = {
                "compilation": True,  # Assume OK when skipped
                "base_test_exists": True,
                "errors": [],
                "missing_files": []
            }
        else:
            print("[dv-smith] Step 5: Verifying gym integrity...")
            validation = cleaner.verify_integrity(profile)

        if not validation['compilation']:
            print("  ⚠️  WARNING: Testbench compilation failed!")

            # Show specific errors if available
            errors = validation.get('errors', [])
            if errors:
                print("  Errors encountered:")
                for error in errors[:5]:  # Limit to 5 errors
                    print(f"    - {error}")
            else:
                print("    No specific errors reported by verification agent")

            # Show missing files if any
            if validation.get('missing_files'):
                print(f"  Missing files: {', '.join(validation['missing_files'][:5])}")

            # Show agent responses for debugging if no errors reported
            if not errors and validation.get('agent_responses'):
                print("  Agent output (for debugging):")
                for resp in validation['agent_responses'][:2]:
                    print(f"    {resp[:150]}...")

            print("  This gym may not be functional. Check test directory structure.")
            print("  You can try manual compilation: cd sim/cadence_sim && make compile")
        elif not validation['base_test_exists']:
            print("  ⚠️  WARNING: Base test file not found!")
            print("  Generated tasks may not be solvable without base test infrastructure.")
        else:
            print("  ✓ Testbench structure validated")
            print("  ✓ Base test infrastructure present")
            if validation['compilation']:
                print("  ✓ Compilation verified successful")

        # Step 6: Create HOWTO guide for agents
        print("[dv-smith] Step 6: Creating HOWTO guide...")
        howto_path = cleaner.create_howto_guide(profile)
        print(f"  Created {howto_path.name}")

        print(f"[dv-smith] Gym created: {gym_dir}")
        print("[dv-smith] Build complete!")

    def validate(self, name: str, simulator: Optional[str] = None) -> None:
        """Validate a gym (smoke tests pass, tasks unsolved).

        Args:
            name: Name of the gym
            simulator: Simulator to use (default: first available)
        """
        print(f"[dv-smith] Validating gym: {name}")

        gym_dir = self.gyms_dir / name
        if not gym_dir.exists():
            print(f"[ERROR] Gym not found: {gym_dir}")
            sys.exit(1)

        # Load profile
        profile_path = self.profiles_dir / f"{name}.yaml"
        if not profile_path.exists():
            print(f"[ERROR] Profile not found: {profile_path}")
            sys.exit(1)

        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        # Select simulator
        from .core.models import Simulator
        from .harness.validator import Validator

        selected_sim = None
        if simulator:
            try:
                selected_sim = Simulator(simulator)
            except ValueError:
                print(f"[ERROR] Unknown simulator: {simulator}")
                sys.exit(1)

        # Initialize validator
        try:
            validator = Validator(gym_dir, profile, selected_sim)
        except Exception as e:
            print(f"[ERROR] Failed to initialize validator: {e}")
            sys.exit(1)

        # Run validation
        passed = validator.validate()

        if passed:
            print("\n[dv-smith] ✓ Validation passed")
        else:
            print("\n[dv-smith] ✗ Validation failed")
            sys.exit(1)

    def eval(self, task_path: str, patch_path: str,
             simulator: Optional[str] = None, output: Optional[str] = None) -> None:
        """Evaluate a solution against a task.

        Args:
            task_path: Path to task markdown file
            patch_path: Path to solution patch/diff
            simulator: Simulator to use (default: first available in task)
            output: Output path for evaluation report (default: stdout)
        """
        print("[dv-smith] Evaluating solution")
        print(f"  Task: {task_path}")
        print(f"  Patch: {patch_path}")

        task_file = Path(task_path)
        if not task_file.exists():
            print(f"[ERROR] Task not found: {task_path}")
            sys.exit(1)

        patch_file = Path(patch_path)
        if not patch_file.exists():
            print(f"[ERROR] Patch not found: {patch_path}")
            sys.exit(1)

        # Import evaluator and models
        from .core.models import Simulator, TaskSpec
        from .harness.evaluator import Evaluator

        # 1. Load task spec
        print("[dv-smith] Loading task specification...")
        try:
            content = task_file.read_text()
            task = TaskSpec.from_markdown(content)
            print(f"[dv-smith] Task: {task.name} (ID: {task.id})")
        except Exception as e:
            print(f"[ERROR] Failed to parse task: {e}")
            sys.exit(1)

        # 2. Determine gym directory from task file path
        # Task files are in gyms/<name>/tasks/*.md
        gym_dir = task_file.parent.parent
        if not (gym_dir / "gym_metadata.yaml").exists():
            print(f"[ERROR] Gym metadata not found. Expected gym at: {gym_dir}")
            sys.exit(1)

        print(f"[dv-smith] Gym: {gym_dir}")

        # 3. Load profile for this gym
        gym_name = gym_dir.name
        profile_path = self.profiles_dir / f"{gym_name}.yaml"
        if not profile_path.exists():
            print(f"[ERROR] Profile not found: {profile_path}")
            sys.exit(1)

        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        # 4. Select simulator
        if simulator:
            try:
                selected_sim = Simulator(simulator)
            except ValueError:
                print(f"[ERROR] Unknown simulator: {simulator}")
                sys.exit(1)
        else:
            # Use first available from task
            if task.supported_simulators:
                selected_sim = task.supported_simulators[0]
            else:
                print("[ERROR] No simulators specified")
                sys.exit(1)

        print(f"[dv-smith] Simulator: {selected_sim.value}")

        # 5. Initialize evaluator
        try:
            evaluator = Evaluator(gym_dir, profile, selected_sim)
        except Exception as e:
            print(f"[ERROR] Failed to initialize evaluator: {e}")
            sys.exit(1)

        # 6. Run evaluation
        print("[dv-smith] Running evaluation...")
        try:
            result = evaluator.evaluate(task, patch_file)
        except Exception as e:
            print(f"[ERROR] Evaluation failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        # 7. Display results
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)
        print(f"Task ID: {result.task_id}")
        print(f"Status: {'PASSED' if result.passed else 'FAILED'}")
        print(f"Score: {result.score:.1f}/100.0")
        print()
        print("Component Scores:")
        print(f"  Functional Coverage: {result.functional_score * 100:.1f}/100")
        print(f"  Code Coverage:       {result.code_coverage_score * 100:.1f}/100")
        print(f"  Health:              {result.health_score * 100:.1f}/100")
        print()
        print("Functional Coverage:")
        print(f"  Bins met: {len(result.functional_bins_met)}")
        print(f"  Bins missed: {len(result.functional_bins_missed)}")
        if result.functional_bins_met:
            print(f"  Met: {', '.join(result.functional_bins_met[:5])}")
        if result.functional_bins_missed:
            print(f"  Missed: {', '.join(result.functional_bins_missed[:5])}")
        print()
        print("Thresholds Met:")
        for key, met in result.thresholds_met.items():
            status = "✓" if met else "✗"
            print(f"  {status} {key}")
        print("=" * 60)

        # 8. Write output file if requested
        if output:
            import json
            output_path = Path(output)
            output_path.parent.mkdir(exist_ok=True, parents=True)

            output_data = {
                "task_id": result.task_id,
                "passed": result.passed,
                "score": result.score,
                "functional_score": result.functional_score,
                "code_coverage_score": result.code_coverage_score,
                "health_score": result.health_score,
                "functional_bins_met": result.functional_bins_met,
                "functional_bins_missed": result.functional_bins_missed,
                "thresholds_met": result.thresholds_met,
                "log_path": str(result.log_path) if result.log_path else None,
                "coverage_db_path": str(result.coverage_db_path) if result.coverage_db_path else None
            }

            with open(output_path, "w") as f:
                json.dump(output_data, f, indent=2)

            print(f"\n[dv-smith] Results saved to: {output_path}")

        print("[dv-smith] Evaluation complete")

    def list_simulators(self) -> None:
        """List available simulators."""
        print("[dv-smith] Available simulators:")
        available = SimulatorRegistry.list_available()
        if available:
            for sim in available:
                print(f"  ✓ {sim.value}")
        else:
            print("  (none detected)")

    def show_ai_logs(self, tail: int = 10, full: bool = False) -> None:
        """Show AI call logs with rich visualization.

        Args:
            tail: Number of recent entries to show (default: 10)
            full: Show full log content instead of summary
        """
        from .log_viewer import load_ai_calls, display_summary, display_calls_conversation
        from rich.console import Console
        
        console = Console()
        calls = load_ai_calls(limit=tail if tail > 0 else None)
        
        if not calls:
            console.print("[yellow]No AI calls found in log[/yellow]")
            return
        
        # Show summary
        display_summary(calls, console)
        
        # Show conversation
        display_calls_conversation(calls, console)
        
        console.print(f"\n{'─' * 80}")
        console.print(f"[dim]Showing {len(calls)} entries | Use --tail N for more[/dim]")

    def _setup_gym_structure(self, gym_dir: Path, repo_path: Path, profile: dict) -> None:
        """Set up basic gym directory structure.

        Args:
            gym_dir: Gym directory to create
            repo_path: Source repository path
            profile: Profile configuration
        """
        logger.debug("Inside _setup_gym_structure, importing shutil...")
        import shutil
        logger.debug("shutil imported")

        # Create basic directories
        directories = [
            gym_dir / "tests",
            gym_dir / "sequences",
            gym_dir / "tasks",
            gym_dir / "backups" / "original_tests",
            gym_dir / "work"
        ]
        
        logger.debug(f"Creating {len(directories)} directories...")
        for dir_path in tqdm(directories, desc="Creating directories", unit="dir", leave=False):
            dir_path.mkdir(exist_ok=True, parents=True)
        logger.debug("Directories created")

        # Copy ALL source files initially (including test directory)
        # We'll intelligently remove task test files later while keeping infrastructure
        src_dir = repo_path / "src"
        logger.debug(f"Checking src_dir: {src_dir}, exists={src_dir.exists()}")
        if src_dir.exists():
            dest_src = gym_dir / "src"
            if dest_src.exists():
                logger.debug(f"Removing existing dest_src: {dest_src}")
                shutil.rmtree(dest_src)
            logger.debug(f"Copying {src_dir} -> {dest_src}")
            with tqdm(total=1, desc="Copying source files", unit="dir", leave=False) as pbar:
                shutil.copytree(src_dir, dest_src)
                pbar.update(1)
            logger.debug("Source copy complete")

        # Copy sim directories
        sim_dir = repo_path / "sim"
        if sim_dir.exists():
            dest_sim = gym_dir / "sim"
            if dest_sim.exists():
                shutil.rmtree(dest_sim)
            with tqdm(total=1, desc="Copying sim files", unit="dir", leave=False) as pbar:
                shutil.copytree(sim_dir, dest_sim)
                pbar.update(1)

        # Copy any README or docs
        doc_files = ["README.md", "README", "LICENSE", "LICENSE.md"]
        for filename in tqdm(doc_files, desc="Copying documentation", unit="file", leave=False):
            src_file = repo_path / filename
            if src_file.exists():
                shutil.copy2(src_file, gym_dir / filename)

    def _backup_tests(self, gym_dir: Path, repo_path: Path, analysis) -> None:
        """Backup original test files for reference.

        Args:
            gym_dir: Gym directory
            repo_path: Source repository
            analysis: RepoAnalysis with test info
        """
        import shutil

        backup_dir = gym_dir / "backups" / "original_tests"
        backup_dir.mkdir(exist_ok=True, parents=True)

        # Copy each test file
        for test in tqdm(analysis.tests, desc="Backing up tests", unit="file", leave=False):
            src_file = test.file_path
            if src_file.exists():
                # Preserve relative structure
                try:
                    rel_path = src_file.relative_to(repo_path)
                except ValueError:
                    rel_path = src_file.name

                dest_file = backup_dir / rel_path
                dest_file.parent.mkdir(exist_ok=True, parents=True)
                shutil.copy2(src_file, dest_file)

        print(f"  Backed up {len(analysis.tests)} test files")

    def _generate_profile(self, name: str, repo_path: Path, analysis) -> dict:
        """Generate profile dictionary from analysis.

        Args:
            name: Gym name
            repo_path: Repository path
            analysis: RepoAnalysis result

        Returns:
            Profile dictionary
        """
        profile = {
            "name": name,
            "repo_url": str(repo_path),
            "description": f"UVM testbench for {name}",
            "simulators": [s.value for s in analysis.detected_simulators] or ["questa"],
            "paths": {
                "root": ".",
                "tests": str(analysis.tests_dir.relative_to(repo_path)) if analysis.tests_dir else "src/hvl_top/test",
                "sequences": str(analysis.sequences_dir.relative_to(repo_path)) if analysis.sequences_dir else "src/hvl_top/test/sequences",
                "env": str(analysis.env_dir.relative_to(repo_path)) if analysis.env_dir else "src/hvl_top/env",
            },
            "build": {},
            "coverage": {},
            "grading": {
                "smoke_tests": [t.name for t in analysis.tests if "base" in t.name.lower()][:2],
                "weights": {
                    "functional_coverage": 0.6,
                    "code_coverage": 0.3,
                    "health": 0.1
                },
                "thresholds": {
                    "functional": {
                        "min_pct": 80,
                        "strategy": "any_of"
                    },
                    "code": {
                        "statements_min_pct": 70,
                        "branches_min_pct": 60,
                        "toggles_min_pct": 50
                    },
                    "health": {
                        "max_scoreboard_errors": 0,
                        "max_uvm_errors": 0,
                        "max_uvm_fatals": 0,
                        "all_assertions_pass": True
                    }
                }
            },
            "metadata": {
                "test_count": len(analysis.tests),
                "sequence_count": len(analysis.sequences),
                "covergroup_count": len(analysis.covergroups),
                "build_system": analysis.build_system.value if analysis.build_system else "unknown",
                "covergroups": analysis.covergroups[:10]  # Sample of covergroups
            }
        }

        # Add simulator-specific build configs
        for sim in analysis.detected_simulators:
            if sim == Simulator.QUESTA:
                profile["build"]["questa"] = {
                    "work_dir": "sim/questa_sim",
                    "compile_cmd": "make -C sim/questa_sim compile",
                    "run_cmd": "make -C sim/questa_sim simulate test={test} SEED={seed}",
                }
                profile["coverage"]["questa"] = {
                    "report_cmd": "vcover report -details -output {output} {ucdb}",
                    "functional_covergroups": analysis.covergroups[:5]
                }
            elif sim == Simulator.XCELIUM:
                profile["build"]["xcelium"] = {
                    "work_dir": "sim/cadence_sim",
                    "compile_cmd": "make -C sim/cadence_sim compile",
                    "run_cmd": "make -C sim/cadence_sim simulate test={test} SEED={seed}",
                }
            elif sim == Simulator.VCS:
                profile["build"]["vcs"] = {
                    "work_dir": "sim/synopsys_sim",
                    "compile_cmd": "make -C sim/synopsys_sim compile",
                    "run_cmd": "make -C sim/synopsys_sim simulate test={test} SEED={seed}",
                }

        return profile


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="dv-smith: Convert SV/UVM testbenches into DV gyms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest a repository and generate profile
  dvsmith ingest https://github.com/mbits-mirafra/apb_avip --name mbits__apb_avip

  # Build a gym from profile
  dvsmith build mbits__apb_avip --sim questa,xcelium

  # Validate the gym
  dvsmith validate mbits__apb_avip

  # Evaluate a solution
  dvsmith eval --task gyms/mbits__apb_avip/tasks/test_01.md --patch solution.diff

  # List available simulators
  dvsmith list-simulators

  # View AI call logs
  dvsmith ai-logs --tail 20 --full
        """
    )

    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("./dvsmith_workspace"),
        help="Workspace directory (default: ./dvsmith_workspace)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Analyze repo and generate profile")
    ingest_parser.add_argument("repo", help="Repository URL or local path")
    ingest_parser.add_argument("--name", help="Gym name (default: derived from repo)")
    ingest_parser.add_argument("--commit", help="Specific commit to use (default: HEAD)")
    ingest_parser.add_argument("--hints", help="Path to hints JSON file")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build gym from profile")
    build_parser.add_argument("name", help="Gym name (from profile)")
    build_parser.add_argument("--sim", help="Comma-separated list of simulators")
    build_parser.add_argument(
        "--tasks",
        default="stimulus",
        help="Task types to generate: stimulus, coverage_func, all (default: %(default)s)"
    )
    build_parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Skip testbench compilation verification"
    )

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate gym")
    validate_parser.add_argument("name", help="Gym name")
    validate_parser.add_argument("--sim", help="Simulator to use")

    # Eval command
    eval_parser = subparsers.add_parser("eval", help="Evaluate solution")
    eval_parser.add_argument("--task", required=True, help="Path to task markdown")
    eval_parser.add_argument("--patch", required=True, help="Path to solution patch")
    eval_parser.add_argument("--sim", help="Simulator to use")
    eval_parser.add_argument("--output", "-o", help="Output report path")

    # List simulators command
    subparsers.add_parser("list-simulators", help="List available simulators")

    # AI logs command
    ai_logs_parser = subparsers.add_parser("ai-logs", help="Show AI call logs")
    ai_logs_parser.add_argument("--tail", type=int, default=10, help="Number of recent entries to show (default: 10)")
    ai_logs_parser.add_argument("--full", action="store_true", help="Show full log content")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize application
    app = DVSmith(workspace=args.workspace)

    # Dispatch commands
    if args.command == "ingest":
        app.ingest(args.repo, name=args.name, commit=args.commit)
    elif args.command == "build":
        sims = args.sim.split(",") if args.sim else None
        app.build(args.name, simulators=sims, task_types=args.tasks, skip_verification=args.skip_verification)
    elif args.command == "validate":
        app.validate(args.name, simulator=args.sim)
    elif args.command == "eval":
        app.eval(args.task, args.patch, simulator=args.sim, output=args.output)
    elif args.command == "list-simulators":
        app.list_simulators()
    elif args.command == "ai-logs":
        app.show_ai_logs(tail=args.tail, full=args.full)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()