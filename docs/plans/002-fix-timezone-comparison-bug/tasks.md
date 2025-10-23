# Tasks: Fix Timezone Comparison Bug

This plan is small and focused - just one bug fix. Tasks are atomic and testable.

## Task 1: Search codebase for START_OF_OPERATION usage

**Goal**: Identify all places where START_OF_OPERATION is used to ensure compatibility.

**Changes**:
None - reconnaissance only.

**Commands**:
```bash
grep -r "START_OF_OPERATION" src/
grep -r "START_OF_OPERATION" tests/
```

**Verification**:
- Document all usages found
- Verify each usage will work with timezone-aware datetime
- Note any potential issues

---

## Task 2: Update START_OF_OPERATION to be timezone-aware

**Goal**: Make START_OF_OPERATION a timezone-aware datetime in Eastern time.

**Changes**:
1. Open `src/dry_bridge/utils.py`
2. Update line 6:

**Before:**
```python
START_OF_OPERATION = datetime(2023, 7, 1)
```

**After:**
```python
START_OF_OPERATION = datetime(2023, 7, 1, tzinfo=ZoneInfo("America/New_York"))
```

**Verification**:
- Run `uv run ruff check src/dry_bridge/utils.py`
- Run `uv run mypy src/dry_bridge/utils.py`
- Code compiles without errors

---

## Task 3: Run full test suite

**Goal**: Ensure all existing tests still pass with timezone-aware constant.

**Changes**:
None - verification only.

**Verification**:
- Run `uv run pytest`
- All tests should pass
- No new failures introduced

---

## Task 4: Test refresh command manually

**Goal**: Verify the bug is fixed and refresh works correctly.

**Test Scenarios**:

1. **Run refresh with database connection**:
   ```bash
   uv run dry-bridge refresh
   ```
   - Expected: No TypeError
   - Expected: Command completes successfully
   - Expected: Proper logging of timestamps

2. **Check the logs**:
   - Verify timestamps are formatted correctly
   - No errors about timezone comparisons
   - Clear progress messages

**Verification**:
- Command runs without crashing
- No TypeError about timezone comparison
- Database operations complete successfully

---

## Task 5: Update tests if needed

**Goal**: Fix any tests that break due to timezone-aware constant.

**Changes**:
Only if tests fail in Task 4.

**Potential Issues**:
- Tests that create datetime objects for comparison might need timezone info
- Tests that mock START_OF_OPERATION might need updates

**Verification**:
- All tests pass
- Test code is clean and simple
- No timezone-naive comparisons remain

---

## Task 6: Final verification

**Goal**: Confirm the fix is complete and robust.

**Verification Checklist**:
- [ ] START_OF_OPERATION is timezone-aware Eastern time
- [ ] `refresh` command runs without TypeError
- [ ] All tests pass
- [ ] Linting passes
- [ ] Type checking passes
- [ ] Manual testing shows correct behavior
- [ ] Code is simpler (no workarounds needed)

**Final Commands**:
```bash
uv run pytest
uv run ruff check .
uv run mypy src/
uv run dry-bridge refresh --help
```

All should succeed with no errors.

---

## Summary

These 6 tasks implement a simple, focused fix:

- **Task 1**: Reconnaissance - find all usages
- **Task 2**: Make the fix - add timezone to constant
- **Task 3**: Verify existing tests pass
- **Task 4**: Manual testing of refresh command
- **Task 5**: Fix any broken tests (if needed)
- **Task 6**: Final verification

The fix is surgical - one line change that makes semantic sense and prevents the bug. Simple, clean, and following constitution principles.
