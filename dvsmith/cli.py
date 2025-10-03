#!/usr/bin/env python3
"""dv-smith CLI - Convert SystemVerilog/UVM testbenches into DV gyms."""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import adapters to trigger registration
from .adapters.sim.base import SimulatorRegistry
from .core.models import Simulator
from .core.task_generator import TaskGenerator

# AI analyzer is required
try:
    from .core.ai_analyzer import AIRepoAnalyzer
except ImportError as e:
    print("[ERROR] Failed to import AI analyzer. Please install required dependencies:")
    print("  pip install anthropic")
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
        print(f"[dv-smith] Ingesting repository: {repo_url}")

        if name is None:
            # Derive name from repo URL
            if repo_url.startswith(("http://", "https://", "git@")):
                # Extract repo name from git URL
                name = repo_url.rstrip("/").split("/")[-1].replace(".git", "").replace("-", "_")
            else:
                name = Path(repo_url).stem.replace("-", "_")

        print(f"[dv-smith] Gym name: {name}")

        # Handle git URLs - clone to workspace
        if repo_url.startswith(("http://", "https://", "git@")):
            import subprocess

            # Clone to a temp directory in workspace
            clones_dir = self.workspace / "clones"
            clones_dir.mkdir(exist_ok=True)

            repo_path = clones_dir / name

            if repo_path.exists():
                print(f"[dv-smith] Repository already cloned at: {repo_path}")
                print("[dv-smith] Using existing clone...")
            else:
                print(f"[dv-smith] Cloning repository to: {repo_path}")
                try:
                    result = subprocess.run(
                        ["git", "clone", repo_url, str(repo_path)],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    if result.returncode != 0:
                        print(f"[ERROR] Failed to clone repository: {result.stderr}")
                        sys.exit(1)
                    print("[dv-smith] Clone successful")
                except subprocess.TimeoutExpired:
                    print("[ERROR] Clone timed out after 5 minutes")
                    sys.exit(1)
                except Exception as e:
                    print(f"[ERROR] Failed to clone: {e}")
                    sys.exit(1)

            # Checkout specific commit if requested
            if commit:
                print(f"[dv-smith] Checking out commit: {commit}")
                try:
                    subprocess.run(
                        ["git", "checkout", commit],
                        cwd=repo_path,
                        capture_output=True,
                        check=True
                    )
                except subprocess.CalledProcessError as e:
                    print(f"[ERROR] Failed to checkout commit: {e.stderr}")
                    sys.exit(1)
        else:
            # Local path
            repo_path = Path(repo_url).resolve()
            if not repo_path.exists():
                print(f"[ERROR] Repository not found: {repo_path}")
                sys.exit(1)

        # Check for Anthropic API key
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("[ERROR] ANTHROPIC_API_KEY environment variable is required")
            print("[ERROR] Set it with: export ANTHROPIC_API_KEY=your-key-here")
            print("[ERROR] Or add it to .env file")
            sys.exit(1)

        # Use AI analyzer
        print("[dv-smith] Using AI-powered analysis...")
        try:
            ai_analyzer = AIRepoAnalyzer(repo_path)
            analysis = ai_analyzer.analyze()

            print(f"  ✓ Found {len(analysis.tests)} tests")
            print(f"  ✓ Found {len(analysis.sequences)} sequences")
            print(f"  ✓ Found {len(analysis.covergroups)} covergroups")
            print(f"  ✓ Build system: {analysis.build_system}")
            print(f"  ✓ Detected simulators: {[s.value for s in analysis.detected_simulators]}")

        except Exception as e:
            print(f"[ERROR] AI analysis failed: {e}")
            print("[ERROR] Please check your ANTHROPIC_API_KEY and try again")
            sys.exit(1)

        # Generate profile
        print("[dv-smith] Generating profile...")
        profile = self._generate_profile(name, repo_path, analysis)

        profile_path = self.profiles_dir / f"{name}.yaml"
        with open(profile_path, "w") as f:
            yaml.dump(profile, f, default_flow_style=False, sort_keys=False)

        print(f"[dv-smith] Profile saved: {profile_path}")
        print("[dv-smith] Ingest complete!")

    def build(self, name: str, simulators: Optional[list[str]] = None, task_types: str = "stimulus") -> None:
        """Build a gym from a profile.

        Args:
            name: Name of the gym/profile
            simulators: List of simulators to support (default: all in profile)
            task_types: Comma-separated task types: stimulus, coverage_func, all
        """
        print(f"[dv-smith] Building gym: {name}")

        profile_path = self.profiles_dir / f"{name}.yaml"
        if not profile_path.exists():
            print(f"[ERROR] Profile not found: {profile_path}")
            sys.exit(1)

        # Load profile
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        repo_path = Path(profile["repo_url"])
        if not repo_path.exists():
            print(f"[ERROR] Repository not found: {repo_path}")
            sys.exit(1)

        if simulators:
            print(f"[dv-smith] Target simulators: {', '.join(simulators)}")
        else:
            print("[dv-smith] Using all simulators from profile")

        # Create gym directory
        gym_dir = self.gyms_dir / name
        gym_dir.mkdir(exist_ok=True, parents=True)

        # Re-analyze to get test details (needed for task generation)
        print("[dv-smith] Re-analyzing repository...")

        # Check for Anthropic API key
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("[ERROR] ANTHROPIC_API_KEY environment variable is required")
            print("[ERROR] Set it with: export ANTHROPIC_API_KEY=your-key-here")
            sys.exit(1)

        try:
            ai_analyzer = AIRepoAnalyzer(repo_path)
            analysis = ai_analyzer.analyze()
        except Exception as e:
            print(f"[ERROR] AI analysis failed: {e}")
            print("[ERROR] Please check your ANTHROPIC_API_KEY and try again")
            sys.exit(1)

        # Step 1: Copy source structure (including tests - we'll clean intelligently)
        print("[dv-smith] Step 1: Setting up gym structure...")
        self._setup_gym_structure(gym_dir, repo_path, profile)

        # Step 1b: Intelligently clean test directory using Claude SDK
        print("[dv-smith] Step 1b: Intelligently cleaning test directory...")
        from .core.gym_cleaner import GymCleaner

        cleaner = GymCleaner(gym_dir, repo_path)
        cleanup_result = cleaner.analyze_and_clean([test.file_path for test in analysis.tests])

        print(f"  Identified {len(cleanup_result['keep'])} infrastructure files to keep")
        print(f"  Removing {len(cleanup_result['remove'])} task test files")

        # Remove only task test files, keep infrastructure
        removed_count = 0
        for test_file_path in cleanup_result['remove']:
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
                print(f"  Warning: Could not remove {test_file.name}: {e}")

        print(f"  Successfully removed {removed_count} task test files")

        # Step 1c: Clean package includes for removed tests
        print("[dv-smith] Step 1c: Cleaning package includes...")
        removed_test_names = [Path(test_file_path).name for test_file_path in cleanup_result['remove']]
        include_cleanup = cleaner.clean_package_includes(removed_test_names)

        if include_cleanup['modified_files']:
            print(f"  Cleaned {len(include_cleanup['modified_files'])} package file(s)")
        if include_cleanup.get('errors'):
            print(f"  ⚠️  Warnings: {len(include_cleanup['errors'])} package cleanup issues")

        # Step 2: Generate task specifications
        print("[dv-smith] Step 2: Generating task specifications...")
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
        tasks = task_gen.generate_tasks_multi(tasks_dir, modes=selected_categories, smoke_tests=smoke_tests)

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
        print("[dv-smith] Step 5: Verifying gym integrity...")
        validation = cleaner.verify_integrity(profile)

        if not validation['compilation']:
            print("  ⚠️  WARNING: Testbench compilation failed!")
            for error in validation.get('errors', [])[:5]:  # Limit to 5 errors
                print(f"    - {error}")
            if validation.get('missing_files'):
                print(f"  Missing files: {', '.join(validation['missing_files'][:5])}")
            print("  This gym may not be functional. Check test directory structure.")
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
        """Show AI call logs.

        Args:
            tail: Number of recent entries to show (default: 10)
            full: Show full log content instead of summary
        """
        from .core.ai_structured import AI_LOG_FILE
        import json

        if not AI_LOG_FILE.exists():
            print(f"[dv-smith] No AI logs found at: {AI_LOG_FILE}")
            return

        print(f"[dv-smith] AI call logs: {AI_LOG_FILE}")
        print()

        # Read all log entries
        entries = []
        with AI_LOG_FILE.open() as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if not entries:
            print("[dv-smith] No log entries found")
            return

        # Show last N entries
        recent_entries = entries[-tail:] if tail > 0 else entries

        for i, entry in enumerate(recent_entries, 1):
            timestamp = entry.get("timestamp", "unknown")
            model = entry.get("response_model", "unknown")
            duration = entry.get("duration_ms", 0)
            error = entry.get("error")

            print(f"[{i}] {timestamp}")
            print(f"    Model: {model}")
            print(f"    Duration: {duration:.0f}ms")

            if full:
                prompt = entry.get("prompt", "")
                print(f"    Prompt: {prompt[:200]}..." if len(prompt) > 200 else f"    Prompt: {prompt}")

                if error:
                    print(f"    Error: {error}")
                else:
                    response = entry.get("response", {})
                    response_str = json.dumps(response, indent=2)
                    if len(response_str) > 300:
                        print(f"    Response: {response_str[:300]}...")
                    else:
                        print(f"    Response: {response_str}")
            else:
                if error:
                    print(f"    Status: ✗ Error - {error[:100]}")
                else:
                    print(f"    Status: ✓ Success")

            print()

        print(f"Showing {len(recent_entries)} of {len(entries)} total entries")
        print(f"Use --tail N to see more entries, or --full for complete details")

    def _setup_gym_structure(self, gym_dir: Path, repo_path: Path, profile: dict) -> None:
        """Set up basic gym directory structure.

        Args:
            gym_dir: Gym directory to create
            repo_path: Source repository path
            profile: Profile configuration
        """
        import shutil

        # Create basic directories
        (gym_dir / "tests").mkdir(exist_ok=True)
        (gym_dir / "sequences").mkdir(exist_ok=True)
        (gym_dir / "tasks").mkdir(exist_ok=True)
        (gym_dir / "backups" / "original_tests").mkdir(exist_ok=True, parents=True)
        (gym_dir / "work").mkdir(exist_ok=True)

        # Copy ALL source files initially (including test directory)
        # We'll intelligently remove task test files later while keeping infrastructure
        src_dir = repo_path / "src"
        if src_dir.exists():
            dest_src = gym_dir / "src"
            if dest_src.exists():
                shutil.rmtree(dest_src)
            shutil.copytree(src_dir, dest_src)

        # Copy sim directories
        sim_dir = repo_path / "sim"
        if sim_dir.exists():
            dest_sim = gym_dir / "sim"
            if dest_sim.exists():
                shutil.rmtree(dest_sim)
            shutil.copytree(sim_dir, dest_sim)

        # Copy any README or docs
        for filename in ["README.md", "README", "LICENSE", "LICENSE.md"]:
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
        for test in analysis.tests:
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
        app.build(args.name, simulators=sims, task_types=args.tasks)
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