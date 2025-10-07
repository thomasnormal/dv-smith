# Gym Cleaner Refactored to Use Structured Responses

## Problem

You correctly identified that `gym_cleaner.py` was doing manual parsing of AI responses - exactly the anti-pattern we just fixed in `ai_structured.py`.

### What was wrong:

1. **`verify_integrity_async`** - Asked for JSON but used `_parse_validation_results()` with:
   - Regex to extract JSON blocks
   - Fallback heuristics like searching for "compilation success" in text
   - Manual error extraction from free-form text

2. **`analyze_and_clean_async`** - Used `_parse_file_list()` with:
   - Regex to find file paths in text
   - JSON extraction attempts
   - Line-by-line parsing

Both methods violated the principle: **"Define clear contracts and enforce them"**

## Solution

### Added Pydantic Models

```python
class ValidationResult(BaseModel):
    """Result of testbench validation."""
    compilation: bool
    base_test_exists: bool
    missing_files: list[str]
    errors: list[str]

class FileList(BaseModel):
    """List of files to keep."""
    files_to_keep: list[str]
```

### Refactored Methods

1. **`verify_integrity_async`**:
   - Now uses `query_with_pydantic_response()` with `ValidationResult` model
   - No manual parsing - gets typed, validated data
   - Clear contract enforced by schema

2. **`analyze_and_clean_async`**:
   - Now uses `query_with_pydantic_response()` with `FileList` model
   - Falls back to heuristics only on exception (not on parse failure)
   - Clear contract enforced by schema

### Removed Code

- ❌ `_parse_file_list()` - 40 lines of regex/JSON parsing deleted
- ❌ `_parse_validation_results()` - 45 lines of heuristic parsing deleted
- ❌ Unused imports: `json`, `re`, `query`, `ClaudeAgentOptions`, etc.

**Total: ~100 lines of brittle parsing code removed**

## Benefits

1. **Consistency**: All structured AI responses now use the same pattern
2. **Type safety**: Get validated Pydantic models, not raw dicts
3. **Maintainability**: Single point of change for response handling
4. **Clarity**: Clear contracts between AI and code
5. **Less fragile**: No regex, no heuristics, no "try JSON then fallback"

## What Stayed

`clean_package_includes_async()` still uses free-form text because it's asking Claude to *edit files*, not return structured data. This is appropriate.

## Impact

Before: 3 different ways to handle AI responses (structured query, manual JSON parsing, free-form)
After: 2 clear patterns (structured via Pydantic, free-form for actions)

The code now follows its own best practices consistently.
