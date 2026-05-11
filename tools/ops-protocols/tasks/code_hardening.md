# Task: Boy Scout Hardening Pass

## Objective
Apply incremental code quality improvements to the runtime codebase without altering
business logic. Each run selects recently untouched files and applies the production standard to them.

## Non-Negotiable Rules
1. **DO NOT change business logic** — Code quality only
2. **DO NOT add dependencies** — Work with what already exists
3. **DO NOT delete existing comments** — Preserve documentation
4. **Every change must pass tests** — Run suite after editing

## Scope per Run
Select **3 files** from `runtime/` that have not been modified
in the most recent commit. Prioritize in this order:
1. Files in `runtime/core/` (critical infrastructure)
2. Files in `runtime/connectors/` (exchange interface)
3. Files in `runtime/api/` (presentation layer)
4. Files in `runtime/modules/` (bot logic)

## Per-File Checklist

### A) Type Hints
- [ ] All public functions have type hints on parameters
- [ ] All public functions have a return type hint
- [ ] Complex types use `Optional`, `Union`, `dict[str, ...]` correctly
- [ ] Imports of `typing` or `__future__.annotations` present if needed

### B) Error Handling
- [ ] No bare `except:` (without exception type)
- [ ] No `except Exception:` that silences errors with `pass`
- [ ] Network operations have timeout and retry
- [ ] Decimal operations have a guard against NaN/Infinity:
  ```python
  # Anti-NaN guard pattern
  if value.is_nan() or value.is_infinite():
      value = Decimal("0")
  ```

### C) Docstrings
- [ ] All classes have a docstring describing their purpose
- [ ] Public functions have a docstring with Args/Returns
- [ ] Module has a top-level docstring

### D) Code Hygiene
- [ ] No stray `print()` calls (use logger)
- [ ] No TODO without ticket/reference
- [ ] No unused imports
- [ ] Magic constants extracted to descriptively named variables

## Execution Steps

### Step 1 — Select Files
```bash
git log --oneline -5 -- runtime/
```
Identify the 3 files with the least recent activity.

### Step 2 — Apply Checklist
For each selected file, apply the 4 checklist blocks.
Document each change made.

### Step 3 — Verify Tests
```bash
python -m pytest runtime/tests/ -v --tb=short
```
If any test fails due to the changes, revert the specific change.

### Step 4 — Report
Generate summary table:
| File | Type Hints | Error Handling | Docstrings | Hygiene | Changes |
|---------|-----------|----------------|------------|---------|---------|
| ...     | ✅/⚠️     | ✅/⚠️          | ✅/⚠️      | ✅/⚠️   | N       |

## Success Criteria
- [ ] 3 files processed
- [ ] All tests still passing
- [ ] At least 1 improvement applied per file
- [ ] Summary table generated
