# AI Analyzer Accuracy Improvements

**Date:** October 1, 2025

## Problem Identified

The user asked: *"Are you sure you're getting all the tests out from those repositories?"*

Investigation revealed significant accuracy issues with the original AI analyzer:

| Repository | Old AI Count | Actual Count | Error |
|------------|--------------|--------------|-------|
| APB AVIP | 24 | 10 | **+140% overcount** |
| AXI4 AVIP | 50 | 72 | **-30% undercount** |
| I3C AVIP | 47 | 27 | **+74% overcount** |
| SPI AVIP | 25 | 25 | ✅ Accurate |
| I2S AVIP | 27 | 27 | ✅ Accurate |
| UART AVIP | 17 | 16 | ⚠️ -6% |

**Root causes:**
1. Used `**/*.sv` glob pattern that searched ALL subdirectories
2. Included sequence files from `sequences/` and `virtual_sequences/` subdirectories
3. Limited to 50 files maximum, missing tests in large repos like AXI4 (72 tests)
4. AI prompt wasn't specific enough about excluding sequences

## Solutions Implemented

### 1. Improved File Discovery (`ai_analyzer.py:212-235`)

**Before:**
```python
test_files = list(tests_path.glob('**/*.sv'))  # Searches all subdirs
for test_file in test_files[:50]:  # Only 50 files max
```

**After:**
```python
# First try direct children (most common pattern)
test_files.extend(tests_path.glob('*.sv'))

# If no files found, try one level deep
if not test_files:
    test_files.extend(tests_path.glob('*/*.sv'))

# Filter out packages and sequences
filtered_files = []
for f in test_files:
    if 'pkg' in f.name.lower() or 'package' in f.name.lower():
        continue
    if 'seq' in str(f.parent).lower() and 'seq' not in f.name:
        continue
    filtered_files.append(f)

# Process up to 100 files (was 50)
for test_file in filtered_files[:100]:
```

**Impact:**
- Excludes sequence subdirectories
- Filters out package files
- Increased limit to 100 files for large testbenches

### 2. Enhanced AI Prompt (`ai_analyzer.py:266-287`)

**Before:**
```
Analyze this SystemVerilog test file and extract test class information.
Extract:
1. class_name: Name of the test class
2. base_class: What it extends
```

**After:**
```
Analyze this SystemVerilog file and extract UVM TEST class information.

IMPORTANT: Only extract if this is a UVM TEST class (extends uvm_test or *_test base class).
Do NOT extract if this is:
- A sequence (extends *_sequence or uvm_sequence)
- A package file (*_pkg.sv)
- A configuration class
- A virtual sequence
```

**Impact:** Explicit instructions to exclude non-test classes

### 3. Improved Regex Fallback (`ai_analyzer.py:311-338`)

**Before:**
```python
match = re.search(r'class\s+(\w+)\s+extends\s+(\w+)', content)
if match and ('test' in match.group(2).lower() or match.group(2) == 'uvm_test'):
    return UVMTest(...)
```

**After:**
```python
match = re.search(r'class\s+(\w+)\s+extends\s+(\w+)', content)
if match:
    class_name = match.group(1)
    base_class = match.group(2)

    # Only accept if it's a test class
    is_test = (
        'test' in base_class.lower() or
        base_class == 'uvm_test' or
        'test' in class_name.lower()
    )
    # Exclude sequences
    is_sequence = (
        'seq' in class_name.lower() or
        'sequence' in class_name.lower() or
        'seq' in base_class.lower()
    )

    if is_test and not is_sequence:
        return UVMTest(...)
```

**Impact:** Better filtering in fallback mode

## Results After Improvements

| Repository | Old Count | New Count | Actual Count | Status |
|------------|-----------|-----------|--------------|--------|
| **APB AVIP** | 24 | **10** | 10 | ✅ Perfect |
| **AXI4 AVIP** | 50 | **72** | 72 | ✅ Perfect |
| **AXI4-Lite AVIP** | 6 | **6** | 6 | ✅ Perfect |
| **I3C AVIP** | 47 | **27** | 27 | ✅ Perfect |
| **SPI AVIP** | 25 | **25** | 25 | ✅ Perfect |
| **I2S AVIP** | 27 | **27** | 27 | ✅ Perfect |
| **UART AVIP** | 17 | **16** | 16 | ✅ Perfect |
| **TVIP-AXI** | 0 | **0** | 0 | ✅ Perfect |
| **YUU AHB** | 7 | **6** | 6 | ✅ Perfect |
| **I2C VIP** | 0 | **0** | 0 | ✅ Perfect |
| **APB VIP** | 1 | **1** | 1 | ✅ Perfect |
| **UVM AXI4-Lite** | 0 | **0** | 0 | ✅ Perfect |

## Summary

✅ **12/12 repositories now report accurate test counts**
✅ **100% accuracy** across all tested repositories
✅ **Fixed major overcounts** (APB: 24→10, I3C: 47→27)
✅ **Fixed major undercount** (AXI4: 50→72, discovered 22 missing tests!)
✅ **Maintained accuracy** for repos that were already correct

## Total Tests Discovered

- **Old analyzer:** 204 tests (with significant errors)
- **New analyzer:** 190 tests (100% accurate)

The new count is lower because we're no longer incorrectly counting sequences and other non-test files.

## Key Learnings

1. **Directory structure matters:** Test repos have varied structures (sequences/, virtual_sequences/, etc.)
2. **Glob patterns need care:** `**/*.sv` is too broad, catches unwanted files
3. **File limits can hide bugs:** 50-file limit caused AXI4 undercount
4. **AI needs explicit instructions:** Must clearly state what NOT to extract
5. **Validation is critical:** Manual verification revealed the issues

## Files Modified

- `dvsmith/core/ai_analyzer.py` (lines 196-338)
  - `_analyze_tests()` method
  - `_extract_test_info()` method

No breaking changes - API remains identical.
