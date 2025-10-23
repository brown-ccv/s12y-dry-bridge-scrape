# Plan: Simplify Load Command

## Current State Analysis

### What's Wrong

The `load` command (lines 89-166 in `__main__.py`) has become overcomplicated:

1. **Unnecessary raw table deduplication**: The raw table has no primary key, duplicates are fine. We're doing complex queries (`get_existing_raw_records`) to avoid them.
2. **Complex deduplication logic**: Lines 310-387 in `load.py` are 77 lines of gnarly SQL generation just to check if raw records exist.
3. **Performance bottleneck**: Checking existence for every raw record is slow and pointless.
4. **Memory still grows**: Loading one file at a time helps, but raw table checking adds overhead.

The current code processes one file at a time (good!) but does too much work per file (bad!).

## Proposed Solution

### Core Principle

**Keep it simple.** The `load` command is for **initial historical loads only**. The `refresh` command handles ongoing updates. Clear tables at start of load to ensure clean slate.

### The Fix

```python
def load(output: str, raw: bool = True, transform: bool = True) -> None:
    """Load extracted data from scratch (clears existing data first)."""
    logger.info(f"Starting load from {output}")
    
    conn = database_connection()
    output_path = Path(output)
    
    # Clear tables at start - load is for initial historical loads
    if raw:
        logger.info("Clearing raw table for fresh load")
        cursor = conn.cursor()
        cursor.execute("TRUNCATE dry_bridge_solar_raw")
        cursor.close()
        conn.commit()
    
    if transform:
        logger.info("Clearing processed table for fresh load")
        cursor = conn.cursor()
        cursor.execute("TRUNCATE dry_bridge_solar_processed CASCADE")
        cursor.close()
        conn.commit()
    
    json_files = sorted(output_path.glob("*.json"))
    total_files = len(json_files)
    logger.info(f"Found {total_files} JSON files to process")
    
    if total_files == 0:
        logger.warning(f"No JSON files found in {output}")
        return
    
    total_raw = 0
    total_transformed = 0
    
    for i, file_path in enumerate(json_files, 1):
        if i % 10 == 0:
            logger.info(f"Progress: {i}/{total_files} files")
        
        try:
            data = json.loads(file_path.read_text())
        except Exception as e:
            logger.error(f"Failed to read {file_path.name}: {e}")
            continue
        
        raw_rows = flatten_raw_data(data)
        
        # Raw table: just insert everything
        if raw:
            load_raw(conn, raw_rows)
            conn.commit()
            total_raw += len(raw_rows)
        
        # Processed table: simple insert (table is empty)
        if transform:
            transformed = transform_raw_data(raw_rows)
            transformed = list(set(transformed))
            transformed.sort(key=lambda x: x.timestamp)
            load_transformed(conn, transformed)
            conn.commit()
            total_transformed += len(transformed)
    
    logger.info(f"Load complete: {total_raw} raw, {total_transformed} processed")
```

**Key changes:**
- Truncate tables at start of load
- No duplicate checking needed (tables are empty)
- Simple, fast inserts
- Load is for historical data only
- Use `refresh` for ongoing updates

## Implementation Steps

### Phase 1: Add table truncation to load()

Update `load()` to clear tables before loading.

**Changes to `__main__.py`:**
1. Find the `load()` function (around line 89)
2. After database connection, before file processing, add truncation:

```python
    conn = database_connection()
    output_path = Path(output)
    
    # Clear tables - load is for initial historical loads only
    if raw:
        logger.info("Clearing raw table for fresh load")
        cursor = conn.cursor()
        cursor.execute("TRUNCATE dry_bridge_solar_raw")
        cursor.close()
        conn.commit()
    
    if transform:
        logger.info("Clearing processed table for fresh load")
        cursor = conn.cursor()
        cursor.execute("TRUNCATE dry_bridge_solar_processed CASCADE")
        cursor.close()
        conn.commit()
```

3. Remove lines 147-161 (existence checking and filtering - no longer needed)
4. Simplify transform block:

```python
        if transform:
            transformed = transform_raw_data(raw_rows)
            transformed = list(set(transformed))
            transformed.sort(key=lambda x: x.timestamp)
            load_transformed(conn, transformed)
            conn.commit()
            total_transformed_loaded += len(transformed)
```

5. Update docstring to clarify: "Load extracted data from scratch (clears existing data first)"

**Verification**:
- Run `uv run ruff check src/dry_bridge/__main__.py`
- Run `uv run mypy src/dry_bridge/__main__.py`
- Code is simple - no deduplication needed

---

### Phase 2: Delete unused deduplication functions

Delete dead code from load.py.

**Changes to load.py**:
1. Open `src/dry_bridge/load.py`
2. Delete `get_existing_timestamps()` function (lines 276-308)
3. Delete `get_existing_raw_records()` function (lines 310-388)

That's 115 lines deleted.

**Verification**:
- Run `uv run ruff check src/dry_bridge/load.py`
- Run `uv run mypy src/dry_bridge/load.py`
- Search codebase to confirm no references:
  ```bash
  grep -r "get_existing_timestamps" src/
  grep -r "get_existing_raw_records" src/
  ```
- Should find no matches

---

### Phase 3: Test historical load

**Goal**: Verify load works for initial historical load.

**Test Steps**:
1. Ensure you have test data in `./output` directory
2. Run load command:
   ```bash
   uv run dry-bridge load --output ./output
   ```
3. Observe logs:
   - Should see "Clearing raw table"
   - Should see "Clearing processed table"
   - Should see progress
4. Check database:
   ```sql
   SELECT COUNT(*) FROM dry_bridge_solar_processed;
   SELECT MIN(timestamp), MAX(timestamp) FROM dry_bridge_solar_processed;
   ```

**Expected Results**:
- Tables cleared at start
- All files processed
- Correct data in database
- No errors

---

### Phase 4: Final verification

**Goal**: Ensure everything works end-to-end.

**Verification Checklist**:
- [ ] `load()` truncates tables at start
- [ ] `load()` processes one file at a time
- [ ] No deduplication logic (not needed)
- [ ] `get_existing_timestamps()` deleted from load.py
- [ ] `get_existing_raw_records()` deleted from load.py
- [ ] Can load historical data successfully
- [ ] All tests pass: `uv run pytest`
- [ ] All linting passes: `uv run ruff check .`
- [ ] All type checking passes: `uv run mypy src/`

**Final smoke test**:
```bash
uv run dry-bridge load --help
uv run dry-bridge load --output ./output
```

Should work without issues.

## Expected Results

### Code Simplification
- **Before**: 115+ lines of complex deduplication logic
- **After**: Simple truncate + insert loop

### Clarity of Purpose
- **Before**: Ambiguous - is load idempotent? Does it update or replace?
- **After**: Clear - load wipes and loads from scratch, refresh handles updates

### Performance
- **Before**: Query database for every file's records to check existence
- **After**: No checks needed, just insert into empty tables

### Reliability
- **Before**: Complex queries could fail in edge cases
- **After**: Simple TRUNCATE and INSERT, battle-tested SQL

## Why This Approach

### Separation of Concerns

**`load` command**: Historical data, initial setup
- Used once to load historical JSON files
- Clears tables first (clean slate)
- Processes all files in output directory
- Simple, fast inserts

**`refresh` command**: Ongoing updates
- Used regularly (scheduled/manual)
- Finds gaps in database
- Fetches missing data from API
- Intelligent retry tracking

This is clearer than having `load` try to be idempotent.

### No Need for ON CONFLICT

Since we truncate tables at the start, there are no existing rows to conflict with. We don't need `ON CONFLICT DO NOTHING` - just regular INSERT.

### Raw Table Is Fine

Raw table has no unique constraint and that's okay:
- It's cleared at start of load
- Only populated during initial historical load
- Refresh command doesn't touch raw table
- If you run load twice, first truncate clears everything

## Summary

The `load` command should be for **initial historical loads only**. It should clear tables and load from scratch.

**The fix**: 
1. Add TRUNCATE at start of load (clear tables first)
2. Remove all deduplication logic (~15 lines)
3. Delete unused deduplication functions (~115 lines)

**Net result**: 
- ~130 lines deleted
- Clear separation: `load` = initial, `refresh` = ongoing
- Much simpler and faster
