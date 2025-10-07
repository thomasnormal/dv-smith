# Build Performance Analysis

## Current Bottleneck: Sequential AI Calls Per Task

### Problem

The `dvsmith build` command makes **6 AI calls per test** sequentially:

```python
def _create_task_for_test(self, test: UVMTest, task_id: int) -> TaskSpec:
    task_name = self._generate_task_name_with_ai(test)              # AI call 1
    level = self._infer_difficulty_with_ai(test)                    # AI call 2
    acceptance = self._create_acceptance_criteria(test)             # AI call 3 (covergroups)
    hints = self._extract_hints_with_ai(test)                       # AI call 4
    description = self._generate_description_with_ai(test)          # AI call 5
    goal = self._generate_goal_with_ai(test)                        # AI call 6
```

### Time Impact

For a repo with **10 tests**:
- 6 AI calls × 10 tests = **60 sequential AI calls**
- Average AI call: ~2-5 seconds
- Total time: **2-5 minutes minimum**

For the test repo with **3 tests**:
- 6 AI calls × 3 tests = **18 sequential AI calls**
- Plus: 3 AI calls for repo analysis
- Plus: 2 AI calls for gym cleaning
- Total: **~23 AI calls**
- Time: **1-2 minutes**

## Why It's Slow

1. **Sequential execution** - Each AI call waits for the previous one
2. **No caching** - Same test analyzed multiple times for different attributes
3. **No batching** - Can't ask for multiple things in one call
4. **Network latency** - Each call has HTTP overhead

## Solutions

### Option 1: Batch AI Calls (Quick Win) ⚡

Instead of 6 separate calls, make **1 call per test** that gets everything:

```python
class TaskMetadata(BaseModel):
    """All task metadata in one response."""
    task_name: str = Field(description="Human-readable task name (2-5 words)")
    difficulty: str = Field(description="EASY, MEDIUM, or HARD")
    description: str = Field(description="Clear task description (2-4 sentences)")
    goal: str = Field(description="Concise goal statement (1-2 sentences)")
    hints: list[str] = Field(default_factory=list, description="3-5 helpful hints")
    covergroups: list[str] = Field(default_factory=list, description="Relevant covergroups")
```

**Impact**: 60 calls → 10 calls = **6x faster**

### Option 2: Parallel Task Generation (Medium Win) 🚀

Generate tasks in parallel using `asyncio.gather`:

```python
async def generate_tasks_async(self, tests: list[UVMTest]) -> list[TaskSpec]:
    """Generate all tasks in parallel."""
    tasks = await asyncio.gather(*[
        self._create_task_for_test_async(test, i)
        for i, test in enumerate(tests)
    ])
    return tasks
```

**Impact**: If API allows 5 concurrent requests, **5x faster**

### Option 3: Combined (Best) 🎯

Batch calls + parallel execution:
- 1 call per test (6x reduction)
- 5 parallel tasks (5x reduction)
- **Total: 30x faster** (2 minutes → 4 seconds)

### Option 4: Cache Analysis Results 💾

Cache the initial repo analysis since build runs it twice:
```python
# In build()
if not reanalyze:
    # Load from profile instead of re-analyzing
    analysis = self._load_analysis_from_profile(profile)
```

**Impact**: Saves ~10-20 seconds

## Recommended Implementation

### Phase 1: Batch AI Calls (Easiest, Biggest Impact)

1. Create `TaskMetadata` Pydantic model with all 6 fields
2. Update `_create_task_for_test` to make 1 AI call
3. Extract fields from single response

**Effort**: 30 minutes
**Speedup**: 6x

### Phase 2: Parallel Execution

1. Make `_create_task_for_test` async
2. Use `asyncio.gather` in `generate_tasks`
3. Handle rate limiting (max 5 concurrent)

**Effort**: 1 hour
**Speedup**: 5x additional (30x total)

### Phase 3: Optimize Gym Cleaning

The gym cleaner also makes AI calls that could be optimized,
but they're only called once (not per-test), so less impact.

## Expected Results

**Current**: 10 tests = ~5 minutes
**After Phase 1**: 10 tests = ~50 seconds (6x faster)
**After Phase 2**: 10 tests = ~10 seconds (30x faster)

The 3-test repo timeout would become: ~2 seconds total
