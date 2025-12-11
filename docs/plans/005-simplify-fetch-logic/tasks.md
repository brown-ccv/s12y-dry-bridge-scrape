# Tasks: Simplify Fetch Logic by Removing Retry Tracking

This file breaks down the plan into small, atomic tasks that can be completed and verified independently.

---

## Task 1: Extract Pure Gap Detection Logic

**Goal**: Extract gap-finding logic into testable function before making other changes

**Changes**:
1. Open `src/dry_bridge/load.py`
2. Add new function before `find_missing_timestamps()` (around line 290):

```python
def compute_missing_timestamps(
    existing_timestamps: set[datetime],
    start: datetime,
    end: datetime,
) -> list[datetime]:
    """
    Compute which 15-minute intervals are missing from a set.
    
    Pure function that compares expected intervals against existing ones.
    
    Args:
        existing_timestamps: Set of timestamps that exist
        start: Start of range to check
        end: End of range to check (inclusive)
    
    Returns:
        List of missing datetime objects (sorted)
    """
    missing = []
    current = start
    delta = timedelta(minutes=15)
    
    while current <= end:
        if current not in existing_timestamps:
            missing.append(current)
        current += delta
    
    return missing
```

3. Update `find_missing_timestamps()` to use it:

```python
def find_missing_timestamps(conn: connection) -> list[datetime]:
    """
    Find all 15-minute intervals missing from the database.
    
    Queries the database for existing timestamps and compares against
    expected intervals from START_OF_OPERATION to now.
    
    Args:
        conn: Active database connection
    
    Returns:
        List of missing datetime objects
    """
    logger.debug("Querying for missing timestamps")
    cursor = database_cursor(conn)
    
    cursor.execute("""
        SELECT timestamp 
        FROM dry_bridge_solar_processed 
        ORDER BY timestamp
    """)
    existing_timestamps = {row[0] for row in cursor.fetchall()}
    
    # Use pure function to compute gaps
    missing = compute_missing_timestamps(
        existing_timestamps,
        START_OF_OPERATION,
        round_down_15min(local_now())
    )
    
    logger.info(f"Found {len(missing)} missing timestamps")
    return missing
```

**Verification**:
```bash
# Check syntax
ruff check src/dry_bridge/load.py

# Test import
python -c "from dry_bridge.load import compute_missing_timestamps, find_missing_timestamps; print('OK')"
```

**Expected**: New function exists, original function uses it, still queries processed table

---

## Task 2: Update find_missing_timestamps() to Check Raw Table

**Goal**: Change gap detection to check `dry_bridge_solar_raw` instead of `dry_bridge_solar_processed`

**Changes**:
1. Open `src/dry_bridge/load.py`
2. Find the `find_missing_timestamps()` function (around line 290)
3. Change the SQL query and add parsing:
   ```python
   # OLD
   cursor.execute("""
       SELECT timestamp 
       FROM dry_bridge_solar_processed 
       ORDER BY timestamp
   """)
   existing_timestamps = {row[0] for row in cursor.fetchall()}
   
   # NEW
   cursor.execute("""
       SELECT DISTINCT timestamp 
       FROM dry_bridge_solar_raw 
       ORDER BY timestamp
   """)
   
   # Parse ISO strings to datetime objects
   existing_timestamps = set()
   for row in cursor.fetchall():
       try:
           ts = iso_to_local(row[0])
           existing_timestamps.add(ts)
       except Exception as e:
           logger.warning(f"Failed to parse timestamp {row[0]}: {e}")
   ```
4. Update docstring to say "Find all 15-minute intervals missing from the RAW data table"
5. Update debug log to say "Querying for missing timestamps in raw data"
6. Update final log to say "Found {len(missing)} missing timestamps in raw data"

**Verification**:
```bash
# Check syntax
ruff check src/dry_bridge/load.py

# Verify queries raw table
grep -A5 "SELECT DISTINCT timestamp" src/dry_bridge/load.py | grep "dry_bridge_solar_raw"
```

**Expected**: Function now queries raw table instead of processed

---

## Task 3: Remove Fetch Attempts Table from init_database()

**Goal**: Stop creating the `dry_bridge_fetch_attempts` table

**Changes**:
1. Open `src/dry_bridge/load.py`
2. Find `init_database()` function (around line 85)
3. In the `create_table_query` string, delete the entire `CREATE TABLE IF NOT EXISTS dry_bridge_fetch_attempts` block:
   ```sql
   CREATE TABLE IF NOT EXISTS dry_bridge_fetch_attempts (
       date DATE PRIMARY KEY,
       attempt_count INTEGER NOT NULL DEFAULT 1,
       status TEXT NOT NULL CHECK (status IN ('empty', 'error', 'success'))
   );
   ```
4. Update the docstring to remove mention of `dry_bridge_fetch_attempts` table

**Verification**:
```bash
# Check table creation code no longer references fetch_attempts
grep -n "fetch_attempts" src/dry_bridge/load.py
# Should only show the functions we'll delete in next task

# Check syntax
ruff check src/dry_bridge/load.py
```

**Expected**: No table creation for fetch_attempts, syntax valid

---

## Task 4: Delete record_fetch_attempt() Function

**Goal**: Remove the `record_fetch_attempt()` function entirely

**Changes**:
1. Open `src/dry_bridge/load.py`
2. Find `record_fetch_attempt()` function (around line 336)
3. Delete the entire function including docstring (approximately 27 lines)
4. Delete from `def record_fetch_attempt(...)` through the end of the function

**Verification**:
```bash
# Verify function is gone
grep -n "def record_fetch_attempt" src/dry_bridge/load.py
# Should return nothing

# Check syntax
ruff check src/dry_bridge/load.py
```

**Expected**: Function deleted, file still valid Python

---

## Task 5: Delete should_skip_date() Function

**Goal**: Remove the `should_skip_date()` function entirely

**Changes**:
1. Open `src/dry_bridge/load.py`
2. Find `should_skip_date()` function (around line 365)
3. Delete the entire function including docstring (approximately 20 lines)
4. Delete from `def should_skip_date(...)` through the end of the function

**Verification**:
```bash
# Verify function is gone
grep -n "def should_skip_date" src/dry_bridge/load.py
# Should return nothing

# Check syntax
ruff check src/dry_bridge/load.py

# Verify load.py still imports properly
python -c "import dry_bridge.load; print('Import OK')"
```

**Expected**: Function deleted, module imports successfully

---

## Task 6: Remove Retry Function Imports from __main__.py

**Goal**: Clean up imports that reference deleted functions

**Changes**:
1. Open `src/dry_bridge/__main__.py`
2. Find the imports from `dry_bridge.load` (around line 15-25)
3. Remove `record_fetch_attempt` from the import list
4. Remove `should_skip_date` from the import list (if present)

**Verification**:
```bash
# Check imports don't reference deleted functions
grep -n "record_fetch_attempt\|should_skip_date" src/dry_bridge/__main__.py
# Should return nothing

# Check syntax
ruff check src/dry_bridge/__main__.py
```

**Expected**: No references to deleted functions in imports

---

## Task 7: Remove Eligible Dates Filtering from refresh()

**Goal**: Remove the retry-based filtering logic

**Changes**:
1. Open `src/dry_bridge/__main__.py`
2. Find the `refresh()` function (around line 177)
3. Find this block (around line 212):
   ```python
   eligible_dates = [
       d
       for d in dates_to_scrape
       if not should_skip_date(conn, d) or d.date() == local_now().date()
   ]
   skipped = len(dates_to_scrape) - len(eligible_dates)
   if skipped > 0:
       logger.info(f"Skipping {skipped} dates due to retry limits")
   
   if not eligible_dates:
       logger.info("No eligible dates to scrape")
       return
   ```
4. Delete that entire block
5. Change the loop to iterate over `dates_to_scrape` directly:
   ```python
   # OLD
   for i, date in enumerate(eligible_dates, 1):
       if i % 10 == 0:
           logger.info(f"Progress: {i}/{total_dates} dates processed")
   
   # NEW
   for i, date in enumerate(dates_to_scrape, 1):
       if i % 10 == 0:
           logger.info(f"Progress: {i}/{total_dates} dates processed")
   ```

**Verification**:
```bash
# Check no references to eligible_dates or should_skip_date
grep -n "eligible_dates\|should_skip_date" src/dry_bridge/__main__.py
# Should return nothing

# Check syntax
ruff check src/dry_bridge/__main__.py
```

**Expected**: Loop processes all dates_to_scrape without filtering

---

## Task 8: Remove record_fetch_attempt() Calls from refresh()

**Goal**: Remove all calls to `record_fetch_attempt()` in the refresh loop

**Changes**:
1. Open `src/dry_bridge/__main__.py`
2. Find the `refresh()` function scraping loop (around line 230)
3. Delete these lines (there should be 4 calls):
   - `record_fetch_attempt(conn, date, "empty")` - when no data available
   - `record_fetch_attempt(conn, date, "success")` - when no missing timestamps
   - `record_fetch_attempt(conn, date, "success")` - after successful load
   - `record_fetch_attempt(conn, date, "error")` - in exception handler
4. Keep the corresponding `conn.commit()` calls for now (we'll clean those up next)

**Verification**:
```bash
# Check no calls to record_fetch_attempt
grep -n "record_fetch_attempt" src/dry_bridge/__main__.py
# Should return nothing

# Check syntax
ruff check src/dry_bridge/__main__.py
```

**Expected**: No more calls to record_fetch_attempt

---

## Task 9: Simplify Commit Logic in refresh()

**Goal**: Remove conditional commits and use single commit at end

**Changes**:
1. Open `src/dry_bridge/__main__.py`
2. Find the `refresh()` function scraping loop (around line 230)
3. Remove all `conn.commit()` calls inside the loop:
   - Remove `conn.commit()` after empty data check
   - Remove `conn.commit()` after no missing timestamps check
   - Remove `conn.commit()` in exception handler
4. Keep only the final `conn.commit()` at the end of the function (after the loop)

**Verification**:
```bash
# Count commits in refresh function - should be 1
grep -A100 "def refresh" src/dry_bridge/__main__.py | grep "conn.commit()" | wc -l
# Should output: 1

# Check syntax
ruff check src/dry_bridge/__main__.py
```

**Expected**: Only one commit at end of refresh function

---

## Task 10: Update refresh() Docstring

**Goal**: Update docstring to reflect new behavior

**Changes**:
1. Open `src/dry_bridge/__main__.py`
2. Find the `refresh()` function docstring (around line 178)
3. Update to remove mentions of retry tracking:
   ```python
   """
   Fill any gaps in the database and add new data.
   
   Queries the RAW data table for missing 15-minute intervals and scrapes
   the necessary dates to fill them. This command automatically detects and
   fills gaps in historical data while also adding new records.
   
   If a scrape fails, the gaps remain and will be retried on the next run.
   There are no retry limits.
   """
   ```

**Verification**:
```bash
# Read the docstring
sed -n '/def refresh/,/"""/p' src/dry_bridge/__main__.py | head -15
# Should show updated docstring

# Check syntax
ruff check src/dry_bridge/__main__.py
```

**Expected**: Docstring reflects new behavior

---

## Task 11: Remove MAX_FETCH_ATTEMPTS from env.example

**Goal**: Remove unused environment variable from example file

**Changes**:
1. Open `env.example`
2. Find any line referencing `MAX_FETCH_ATTEMPTS`
3. Delete that line (if present)

**Verification**:
```bash
# Check for any remaining references
grep -n "MAX_FETCH_ATTEMPTS" env.example
# Should return nothing (or file doesn't exist)
```

**Expected**: No reference to MAX_FETCH_ATTEMPTS

---

## Task 12: Update README.md

**Goal**: Remove retry logic documentation and add migration note

**Changes**:
1. Open `README.md`
2. Search for any mentions of:
   - `MAX_FETCH_ATTEMPTS`
   - Retry logic
   - Retry limits
3. Remove or update those sections
4. Add a note about the fetch_attempts table:
   ```markdown
   ## Database Migration
   
   The `dry_bridge_fetch_attempts` table is no longer used and can be dropped:
   ```sql
   DROP TABLE IF EXISTS dry_bridge_fetch_attempts;
   ```
   ```

**Verification**:
```bash
# Check for remaining references to retry logic
grep -n "MAX_FETCH_ATTEMPTS\|retry limit" README.md
# Should return nothing (or only in migration notes)
```

**Expected**: Documentation updated, migration note added

---

## Task 13: Test Gap Detection - Empty Set



**Goal**: Test pure logic with no existing data

**Changes**:
1. Create `tests/test_gap_detection.py`:

```python
import unittest
from datetime import datetime, timedelta
from dry_bridge.load import compute_missing_timestamps


class TestComputeMissingTimestamps(unittest.TestCase):
    def test_empty_existing_timestamps(self):
        """When no timestamps exist, all should be missing."""
        existing = set()
        start = datetime(2024, 1, 1, 0, 0)
        end = datetime(2024, 1, 1, 1, 0)
        
        result = compute_missing_timestamps(existing, start, end)
        
        # Should have 5 timestamps: 00:00, 00:15, 00:30, 00:45, 01:00
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], datetime(2024, 1, 1, 0, 0))
        self.assertEqual(result[1], datetime(2024, 1, 1, 0, 15))
        self.assertEqual(result[4], datetime(2024, 1, 1, 1, 0))
```

**Verification**:
```bash
python -m pytest tests/test_gap_detection.py::TestComputeMissingTimestamps::test_empty_existing_timestamps -v
```

**Expected**: Test passes, validates empty set behavior

---

## Task 14: Test Gap Detection - With Gaps

**Goal**: Test pure logic finds gaps in middle of data

**Changes**:
1. Add test to `tests/test_gap_detection.py`:

```python
def test_gap_in_middle(self):
    """Missing timestamp in middle should be detected."""
    start = datetime(2024, 1, 1, 0, 0)
    
    # Existing: 00:00, 00:15, 00:45 (missing 00:30)
    existing = {
        datetime(2024, 1, 1, 0, 0),
        datetime(2024, 1, 1, 0, 15),
        datetime(2024, 1, 1, 0, 45),
    }
    end = datetime(2024, 1, 1, 0, 45)
    
    result = compute_missing_timestamps(existing, start, end)
    
    # Should find only the 00:30 gap
    self.assertEqual(len(result), 1)
    self.assertEqual(result[0], datetime(2024, 1, 1, 0, 30))

def test_multiple_gaps(self):
    """Multiple missing timestamps should all be detected."""
    start = datetime(2024, 1, 1, 0, 0)
    
    # Existing: only 00:00 and 01:00 (missing 00:15, 00:30, 00:45)
    existing = {
        datetime(2024, 1, 1, 0, 0),
        datetime(2024, 1, 1, 1, 0),
    }
    end = datetime(2024, 1, 1, 1, 0)
    
    result = compute_missing_timestamps(existing, start, end)
    
    # Should find 3 gaps
    self.assertEqual(len(result), 3)
    self.assertIn(datetime(2024, 1, 1, 0, 15), result)
    self.assertIn(datetime(2024, 1, 1, 0, 30), result)
    self.assertIn(datetime(2024, 1, 1, 0, 45), result)
```

**Verification**:
```bash
python -m pytest tests/test_gap_detection.py -v
```

**Expected**: Tests pass, validates gap detection logic

---

## Task 15: Test Gap Detection - Complete Data

**Goal**: Test pure logic returns empty when no gaps

**Changes**:
1. Add test to `tests/test_gap_detection.py`:

```python
def test_complete_data(self):
    """When all timestamps exist, none should be missing."""
    start = datetime(2024, 1, 1, 0, 0)
    end = datetime(2024, 1, 1, 1, 0)
    
    # Create complete set
    existing = set()
    current = start
    delta = timedelta(minutes=15)
    while current <= end:
        existing.add(current)
        current += delta
    
    result = compute_missing_timestamps(existing, start, end)
    
    # Should find no gaps
    self.assertEqual(len(result), 0)

def test_result_is_sorted(self):
    """Result should be sorted even if existing set is not."""
    start = datetime(2024, 1, 1, 0, 0)
    end = datetime(2024, 1, 1, 1, 0)
    
    # Add timestamps in random order
    existing = {
        datetime(2024, 1, 1, 0, 45),
        datetime(2024, 1, 1, 0, 0),
    }
    
    result = compute_missing_timestamps(existing, start, end)
    
    # Result should be sorted
    self.assertEqual(result, sorted(result))
```

**Verification**:
```bash
python -m pytest tests/test_gap_detection.py -v
```

**Expected**: All tests pass, validates complete data handling

---

## Task 16: Final Verification

**Goal**: Confirm all changes are complete and working

**Checks**:
```bash
# No references to deleted functions
grep -r "record_fetch_attempt\|should_skip_date" src/ --include="*.py"
# Should return nothing

# No references to fetch_attempts table
grep -r "fetch_attempts" src/ --include="*.py"
# Should return nothing

# No references to MAX_FETCH_ATTEMPTS
grep -r "MAX_FETCH_ATTEMPTS" . --include="*.py" --include="*.md" --include="*.example"
# Should only be in old plan documents

# Code quality
ruff check src/

# Import test
python -c "from dry_bridge import __main__; from dry_bridge.load import find_missing_timestamps; print('OK')"
```

**Expected**: Clean codebase with no references to deleted code, all imports work

---

## Summary Checklist

After completing all tasks, verify:
- [ ] `find_missing_timestamps()` queries `dry_bridge_solar_raw` table
- [ ] `dry_bridge_fetch_attempts` table is not created
- [ ] `record_fetch_attempt()` function deleted
- [ ] `should_skip_date()` function deleted
- [ ] All imports cleaned up in `__main__.py`
- [ ] Refresh processes all `dates_to_scrape` without filtering
- [ ] No `record_fetch_attempt()` calls in refresh
- [ ] Single commit at end of refresh
- [ ] Docstrings updated
- [ ] Documentation updated (README, env.example)
- [ ] All tests pass (empty database, gaps, complete, transformation)
- [ ] No linting errors
- [ ] Code is simpler (~70 lines removed)
