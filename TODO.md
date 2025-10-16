# TODO - Future Enhancements

## High Priority

- [ ] Docker-based agent execution
  - Add `--docker` flag to `dvsmith run`
  - Use CVDP harness (docker-compose.yml) for execution
  - Requires VERIF_EDA_IMAGE environment variable
  - Provides isolated, reproducible environment

- [ ] Complete evaluate command in Typer CLI
  - Port evaluation logic from old CLI
  - Add live feed for evaluation process
  - Support CVDP harness evaluation mode

## Medium Priority

- [ ] Pluggy-based plugin system for simulators
  - Allow third-party simulator adapters
  - Entry points in pyproject.toml
  - No need to modify core code

- [ ] Disk caching for expensive operations
  - Cache file tree generation
  - Cache AI directory detection (keyed by repo hash)
  - Speed up re-analysis

- [ ] Validate command with simulator
  - Run actual smoke tests
  - Verify compilation works
  - Check task solvability

## Low Priority

- [ ] `--quiet` and `--verbose` flags
  - Quiet: Minimal output
  - Verbose: Show all AI calls, tool usage

- [ ] Prefect flows for complex pipelines
  - Orchestrate: ingest → build → validate
  - Retry failed steps
  - Artifact persistence

- [ ] Web dashboard
  - Visualize workspace
  - Browse tasks
  - View evaluation results

- [ ] Batch processing
  - Process multiple repos at once
  - Parallel ingestion
  - Aggregate statistics

## In Progress

- [ ] Docker-based agent execution (runner.py created, --docker flag added)
- [ ] Complete evaluate command (placeholder working, full eval TODO)

## Done ✅

- [x] Async architecture
- [x] Typer + Rich CLI (8 commands)
- [x] Pydantic Settings
- [x] CVDP export
- [x] Live agent feed
- [x] TypeAdapter for dataclasses
- [x] Retry logic (tenacity)
- [x] Thread-safe logging (filelock)
- [x] Build command with --max-tasks
- [x] Sequence detection (nested fallback)
- [x] Agent runner (dvsmith run)
- [x] Clean architecture (reusable utilities)
- [x] Old CLI removed (966 lines deleted)
- [x] Single AI call for analysis (917 → 106 lines)
- [x] Modular command structure
- [x] Remove analysis_cache complexity
- [x] All imports at file top
- [x] Use Pydantic model_dump() (removed custom to_dict)
- [x] coverage_components field rename
- [x] Early exit after FinalAnswer
