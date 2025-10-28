# Tasks: Simplify Load Command

This file breaks down the load simplification into small, atomic tasks. Each task should take 15-30 minutes and produce a working, testable change.

## Task 1: Add table truncation to load()

**Goal**: Clear tables at start of load - establish that load is for initial historical loads only.

**Changes to __main__.py**:
1. Open `src/dry_bridge/__main__.py`
2. Find the `load()` function (around line 89)
3. After database connection, before file processing loop, add:

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

4. Update function docstring to clarify purpose:
   ```python
   """Load extracted data from scratch (clears existing data first)."""
   ```

**Verification**:
- Run `uv run ruff check src/dry_bridge/__main__.py`
- Run `uv run mypy src/dry_bridge/__main__.py`
- Tables will be cleared at start of load

---

## Task 2: Remove deduplication logic from load()

**Goal**: Simplify load() - no need to check for duplicates since tables are empty.

**Changes to __main__.py**:
1. Find lines 147-161 (existence checking and filtering)
2. Delete those lines entirely
3. Replace with simple insert:

```python
        # Processed table: simple insert (tables are empty)
        if transform:
            transformed = transform_raw_data(raw_rows)
            transformed = list(set(transformed))
            transformed.sort(key=lambda x: x.timestamp)
            load_transformed(conn, transformed)
            conn.commit()
            total_transformed_loaded += len(transformed)
```

4. Update final log message (around line 163):

```python
    logger.info(
        f"Load complete: {total_files} files processed. "
        f"Raw: {total_raw_loaded} rows. "
        f"Processed: {total_transformed_loaded} rows."
    )
```

**Verification**:
- Run `uv run ruff check src/dry_bridge/__main__.py`
- Run `uv run mypy src/dry_bridge/__main__.py`
- Run `uv run pytest`
- Code is simpler - just insert, no checks

---

## Task 3: Delete unused deduplication functions

**Goal**: Remove 115 lines of dead code.

**Changes to load.py**:
1. Open `src/dry_bridge/load.py`
2. Delete `get_existing_timestamps()` function (lines 276-308)
3. Delete `get_existing_raw_records()` function (lines 310-388)

**Verification**:
- Run `uv run ruff check src/dry_bridge/load.py`
- Run `uv run mypy src/dry_bridge/load.py`
- Run `uv run pytest`
- Search codebase to confirm no references:
  ```bash
  grep -r "get_existing_timestamps" src/
  grep -r "get_existing_raw_records" src/
  ```
- Should find no matches

---

## Task 4: Test historical load

**Goal**: Verify load works for initial historical data load.

**Test Steps**:
1. Ensure you have test data in `./output` directory (1+ weeks of JSON files)
2. Ensure database has some existing data (or create some test data)
3. Run load command:
   ```bash
   uv run dry-bridge load --output ./output
   ```
4. Observe logs:
   - Should see "Clearing raw table for fresh load"
   - Should see "Clearing processed table for fresh load"
   - Should see "Progress: 10/X files" etc.
5. Check database:
   ```sql
   SELECT COUNT(*) FROM dry_bridge_solar_processed;
   SELECT MIN(timestamp), MAX(timestamp) FROM dry_bridge_solar_processed;
   ```

**Expected Results**:
- Old data is gone (tables cleared)
- All files processed successfully
- Progress logs appear every 10 files
- Correct row count in database
- No errors

---

## Task 5: Final verification

**Goal**: Ensure everything works end-to-end.

**Verification Checklist**:
- [ ] `load()` truncates tables at start
- [ ] `load()` processes one file at a time
- [ ] No deduplication logic (not needed)
- [ ] `get_existing_timestamps()` deleted from load.py
- [ ] `get_existing_raw_records()` deleted from load.py
- [ ] Can load historical data successfully
- [ ] Old data is cleared (fresh load)
- [ ] All tests pass: `uv run pytest`
- [ ] All linting passes: `uv run ruff check .`
- [ ] All type checking passes: `uv run mypy src/`

**Final smoke test**:
```bash
uv run dry-bridge load --help
uv run dry-bridge load --output ./output
```

Should work without issues.

---

## Summary

These 5 tasks simplify the load command and clarify its purpose:

- **Task 1**: Add table truncation at start (clear slate)
- **Task 2**: Remove deduplication logic (~15 lines)
- **Task 3**: Delete unused functions (~115 lines)
- **Task 4**: Test historical load
- **Task 5**: Final verification

**Net result**: 
- ~130 lines deleted
- Clear purpose: `load` = initial historical, `refresh` = ongoing
- Much simpler and faster
