# Plan: Fix Timezone Comparison Bug in Refresh System

## Problem Statement

The `refresh` command crashes with a `TypeError` when comparing timestamps in `find_missing_timestamps()`. The issue occurs at line 321 in `load.py`:

```python
while current <= end:
```

**Root Cause**: Comparing timezone-naive datetime with timezone-aware datetime:
- `current` starts as `START_OF_OPERATION = datetime(2023, 7, 1)` (naive, no timezone)
- `end` comes from `round_down_15min(local_now())` which returns a timezone-aware datetime (Eastern time)
- Database timestamps are stored in UTC (timezone-aware)

**Error Message**:
```
TypeError: can't compare offset-naive and offset-aware datetimes
```

## Current State Analysis

### Timezone Usage Across Codebase

1. **Database Storage**: All timestamps stored in UTC (timezone-aware)
2. **START_OF_OPERATION**: Naive datetime `datetime(2023, 7, 1)` - no timezone info
3. **local_now()**: Returns Eastern time (timezone-aware)
4. **round_down_15min()**: Preserves timezone from input
5. **find_missing_timestamps()**: Compares all three types

### The Constitution Says

From `docs/constitution.md`:
- **Timezone Handling**: "UTC for storage, Eastern for display, ZoneInfo for conversions"
- **Philosophy**: "Favor simplicity over cleverness"
- **Error Handling**: "Fail loudly, log clearly"

## Proposed Solution

### Core Principle

**Make START_OF_OPERATION timezone-aware in Eastern time**, matching the intent that July 1, 2023 was a local date, not a UTC moment.

### Approach

1. **Update START_OF_OPERATION constant** to be timezone-aware Eastern time
2. **Update find_missing_timestamps()** to ensure consistent timezone usage
3. **Verify all comparisons** work with timezone-aware datetimes

### Why This Approach

- **Minimal changes**: One constant definition + clear documentation
- **Semantically correct**: July 1, 2023 refers to local date at the solar farm
- **Consistent**: All datetime operations will use timezone-aware objects
- **Simple**: No complex conversion logic needed throughout codebase

## Implementation Details

### Change 1: Update START_OF_OPERATION in utils.py

**Before:**
```python
START_OF_OPERATION = datetime(2023, 7, 1)
```

**After:**
```python
START_OF_OPERATION = datetime(2023, 7, 1, tzinfo=ZoneInfo("America/New_York"))
```

### Change 2: No changes needed in find_missing_timestamps()

The function already works correctly once START_OF_OPERATION is timezone-aware:
- `current` starts with Eastern timezone
- `end` has Eastern timezone from `local_now()`
- Database timestamps are UTC, but set lookups work correctly

## Testing Strategy

### Unit Tests
1. Verify START_OF_OPERATION has timezone info
2. Test find_missing_timestamps() with timezone-aware timestamps
3. Test comparisons between START_OF_OPERATION and local_now()

### Integration Tests
1. Run `refresh` command with empty database
2. Run `refresh` command with gaps in data
3. Run `refresh` command with complete data
4. Verify no TypeError occurs

### Manual Verification
1. Run refresh command successfully
2. Check logs for proper timestamp handling
3. Verify data loads correctly into database

## Benefits

1. **Fix the bug**: Eliminates TypeError immediately
2. **Semantic correctness**: START_OF_OPERATION now clearly represents a local moment
3. **Consistency**: All datetime operations use timezone-aware objects
4. **Simplicity**: Single constant change, no complex logic
5. **Future-proof**: Prevents similar timezone comparison issues

## Risks and Mitigations

### Risk: Existing code assumes naive datetime
**Mitigation**: Search codebase for all uses of START_OF_OPERATION and verify compatibility

### Risk: Tests might fail with timezone-aware constant
**Mitigation**: Update tests if needed, verify all pass before merging

### Risk: Other timezone comparison bugs lurking
**Mitigation**: Run full test suite, do manual refresh testing

## Rollback Plan

If issues arise:
1. Revert START_OF_OPERATION to naive datetime
2. Add explicit timezone conversion in find_missing_timestamps()
3. Document the workaround for future cleanup

## Success Criteria

- [ ] `refresh` command runs without TypeError
- [ ] All existing tests pass
- [ ] Manual testing shows correct behavior
- [ ] Code is simpler and clearer
- [ ] No new timezone comparison bugs introduced
