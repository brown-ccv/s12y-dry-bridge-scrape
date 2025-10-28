# Tasks: Simplify Retry Logic

This file breaks down the plan into small, atomic tasks that can be completed and verified independently. Each task should take 15-30 minutes and produce a working, testable change.

## Task 1: Add `group_by_date()` to load.py with tests

**Goal**: Add helper function to convert timestamps to unique dates and test it.

**Changes to load.py**:
1. Open `src/dry_bridge/load.py`
2. Ensure `from datetime import datetime` is imported (should already exist)
3. Add new function at the end of the file (after `most_recent_record()`):

```python
def group_by_date(timestamps: list[datetime]) -> list[datetime]:
    """
    Group timestamps into unique dates.
    
    Converts a list of timestamps to unique dates for scraping,
    since the API works on a per-day basis.
    
    Args:
        timestamps: List of datetime objects
        
    Returns:
        List of datetime objects representing unique dates
    """
    unique_dates = set()
    for ts in timestamps:
        unique_dates.add(ts.date())
    
    # Convert back to datetime objects for scraping
    result = []
    for date in sorted(unique_dates):
        result.append(datetime.combine(date, datetime.min.time()))
    
    return result
```

**Changes to tests**:
1. Create `tests/load_test.py`
2. Add tests for `group_by_date()`:

```python
import unittest
from datetime import datetime

from dry_bridge.load import group_by_date


class TestGroupByDate(unittest.TestCase):
    def test_single_date(self):
        """Test grouping timestamps from single date."""
        timestamps = [
            datetime(2023, 8, 1, 0, 0),
            datetime(2023, 8, 1, 0, 15),
            datetime(2023, 8, 1, 0, 30),
        ]
        result = group_by_date(timestamps)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], datetime(2023, 8, 1, 0, 0))
    
    def test_multiple_dates(self):
        """Test grouping timestamps from multiple dates."""
        timestamps = [
            datetime(2023, 8, 1, 0, 0),
            datetime(2023, 8, 1, 0, 15),
            datetime(2023, 8, 2, 0, 0),
            datetime(2023, 8, 3, 12, 30),
        ]
        result = group_by_date(timestamps)
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], datetime(2023, 8, 1, 0, 0))
        self.assertEqual(result[1], datetime(2023, 8, 2, 0, 0))
        self.assertEqual(result[2], datetime(2023, 8, 3, 0, 0))
    
    def test_empty_list(self):
        """Test grouping empty timestamp list."""
        result = group_by_date([])
        self.assertEqual(len(result), 0)
    
    def test_unsorted_timestamps(self):
        """Test that result is sorted even with unsorted input."""
        timestamps = [
            datetime(2023, 8, 3, 12, 30),
            datetime(2023, 8, 1, 0, 15),
            datetime(2023, 8, 2, 0, 0),
        ]
        result = group_by_date(timestamps)
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], datetime(2023, 8, 1, 0, 0))
        self.assertEqual(result[1], datetime(2023, 8, 2, 0, 0))
        self.assertEqual(result[2], datetime(2023, 8, 3, 0, 0))
```

**Verification**:
- Run `uv run ruff check src/dry_bridge/load.py tests/load_test.py`
- Run `uv run mypy src/dry_bridge/load.py`
- Run `uv run pytest tests/load_test.py -v`
- All tests should pass
- Simple, readable code with no clever tricks

---

## Task 2: Add `find_missing_timestamps()` to load.py with tests

**Goal**: Add database gap detection function and test the logic.

**Changes to load.py**:
1. Open `src/dry_bridge/load.py`
2. Add required imports at top of file:
   - `from datetime import timedelta` (add to existing datetime import)
   - `from .utils import START_OF_OPERATION, round_down_15min, local_now`
3. Add new function after `group_by_date()`:

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
    cursor = conn.cursor()
    
    # Get all existing timestamps from database
    cursor.execute("""
        SELECT timestamp 
        FROM dry_bridge_solar_processed 
        ORDER BY timestamp
    """)
    existing_timestamps = {row[0] for row in cursor.fetchall()}
    
    # Generate all expected timestamps (every 15 minutes)
    missing = []
    current = START_OF_OPERATION
    end = round_down_15min(local_now())
    delta = timedelta(minutes=15)
    
    while current <= end:
        if current not in existing_timestamps:
            missing.append(current)
        current += delta
    
    logger.info(f"Found {len(missing)} missing timestamps")
    return missing
```

**Changes to tests**:
1. Open `tests/load_test.py`
2. Add a new test class to test the timestamp generation logic (not database):

```python
from datetime import timedelta
from dry_bridge.utils import START_OF_OPERATION, round_down_15min


class TestTimestampGeneration(unittest.TestCase):
    def test_15_minute_intervals(self):
        """Test that we generate correct 15-minute intervals."""
        # Generate a few 15-minute intervals
        timestamps = []
        current = START_OF_OPERATION
        delta = timedelta(minutes=15)
        
        for _ in range(4):
            timestamps.append(current)
            current += delta
        
        # Verify they're exactly 15 minutes apart
        self.assertEqual(timestamps[0].minute, 0)
        self.assertEqual(timestamps[1].minute, 15)
        self.assertEqual(timestamps[2].minute, 30)
        self.assertEqual(timestamps[3].minute, 45)
    
    def test_round_down_15min(self):
        """Test rounding down to 15-minute intervals."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        # Test various times round down correctly
        test_time = datetime(2023, 8, 1, 10, 17, 30, tzinfo=ZoneInfo("America/New_York"))
        rounded = round_down_15min(test_time)
        self.assertEqual(rounded.minute, 15)
        self.assertEqual(rounded.second, 0)
        
        test_time = datetime(2023, 8, 1, 10, 44, 59, tzinfo=ZoneInfo("America/New_York"))
        rounded = round_down_15min(test_time)
        self.assertEqual(rounded.minute, 30)
        self.assertEqual(rounded.second, 0)
```

**Verification**:
- Run `uv run ruff check src/dry_bridge/load.py tests/load_test.py`
- Run `uv run mypy src/dry_bridge/load.py`
- Run `uv run pytest tests/load_test.py -v`
- All tests should pass
- Tests verify the logic, not database operations

---

## Task 3: Remove `Metadata` class from scrape.py

**Goal**: Delete the entire Metadata class and related code.

**Changes**:
1. Open `src/dry_bridge/scrape.py`
2. Delete lines 28-93 (the entire `Metadata` class including docstrings)
   - Delete the `@dataclass` line
   - Delete the class definition
   - Delete all methods: `save()` and `load()`
3. Remove `from dataclasses import dataclass` from imports (if not used elsewhere)
4. Keep all other imports unchanged

**Verification**:
- Run `uv run ruff check src/dry_bridge/scrape.py`
- Run `uv run mypy src/dry_bridge/scrape.py` (will show errors - that's expected)
- Confirm ~90 lines were removed
- No Metadata references remain in the file
- Run `uv run pytest` - existing tests should still pass

---

## Task 4: Simplify `scrape()` function in scrape.py

**Goal**: Remove resume parameter and metadata logic from main scrape function.

**Changes**:
1. Open `src/dry_bridge/scrape.py`
2. Update function signature:
   - Change from: `def scrape(start: datetime, end: datetime, resume: bool, output: Path) -> None:`
   - Change to: `def scrape(start: datetime, end: datetime, output: Path) -> None:`
3. Update docstring to remove resume parameter documentation
4. Replace function body with:

```python
def scrape(start: datetime, end: datetime, output: Path) -> None:
    """
    Scrape date range and save to files.
    
    This is a one-time operation for historical data import. Re-run to
    resume - it automatically skips existing files.
    
    Args:
        start: Start date for scraping
        end: End date for scraping
        output: Directory to save downloaded files
    """
    logger.info(f"Scraping from {start} to {end}, output={output}")
    
    if not output.exists():
        logger.info(f"Creating output directory: {output}")
        output.mkdir()
    
    client = scrape_client()
    scrape_range(client, start, end, output)
    
    logger.info("Scrape completed")
```

**Verification**:
- Run `uv run ruff check src/dry_bridge/scrape.py`
- Run `uv run mypy src/dry_bridge/scrape.py`
- No metadata references in function
- Simpler, clearer logic
- Run `uv run pytest` - existing tests should still pass

---

## Task 5: Simplify `scrape_range()` function in scrape.py

**Goal**: Remove metadata parameter and success/failure tracking.

**Changes**:
1. Open `src/dry_bridge/scrape.py`
2. Update function signature:
   - Change from: `def scrape_range(client: httpx.Client, start: datetime, end: datetime, output: Path, metadata: Metadata) -> Metadata:`
   - Change to: `def scrape_range(client: httpx.Client, start: datetime, end: datetime, output: Path) -> None:`
3. Update docstring to remove metadata parameter and return value
4. Replace function body with:

```python
def scrape_range(client: httpx.Client, start: datetime, end: datetime, output: Path) -> None:
    """
    Download solar data for each day in the specified date range.
    
    This function performs the actual HTTP requests to the solar dashboard API,
    handling authentication through cookies. Each day's data is saved as a
    separate JSON file.
    
    Args:
        client: HTTP client with authentication cookies
        start: Start date for the range
        end: End date for the range
        output: Directory to save JSON files
    """
    logger.info(f"Scraping range from {start} to {end}")
    current_date = start
    day_count = 0
    
    while current_date < end:
        current_date += timedelta(days=1)
        day_count += 1
        
        date_str = current_date.strftime("%Y-%m-%d")
        output_file = output / f"{date_str}.json"
        
        # Skip if already scraped
        if output_file.exists():
            logger.debug(f"Skipping {date_str}, file already exists")
            continue
        
        logger.info(f"Processing day {day_count}: {date_str}")
        
        try:
            data = scrape_date(client, current_date)
            
            if len(data["data"]) > 0:
                logger.info(f"Successfully scraped {len(data['data'])} data points for {date_str}")
                
                with open(output_file, "w") as f:
                    f.write(json.dumps(data, indent=2, sort_keys=True))
                
                logger.debug(f"Wrote {output_file.stat().st_size} bytes to {output_file}")
            else:
                logger.warning(f"No data in response for {date_str}")
        
        except (httpx.HTTPError, Exception) as e:
            logger.error(f"Failed to scrape {date_str}: {e}")
            # Continue with next date
    
    logger.info(f"Completed scraping {day_count} days")
```

**Verification**:
- Run `uv run ruff check src/dry_bridge/scrape.py`
- Run `uv run mypy src/dry_bridge/scrape.py`
- No metadata tracking
- Simple error handling: log and continue
- File existence check for idempotency
- Run `uv run pytest` - all tests should still pass

---

## Task 6: Update `extract()` command in __main__.py

**Goal**: Remove resume parameter from CLI command.

**Changes**:
1. Open `src/dry_bridge/__main__.py`
2. Update the `extract()` function signature:
   - Remove: `resume: Annotated[bool, typer.Option(help="resume previous scrape")] = False,`
3. Update the docstring:
   - Change description to: "Extract solar production data from the web dashboard for one-time historical import."
   - Add note: "Re-run to resume - automatically skips existing files."
   - Remove resume parameter documentation
4. Update the function call to `scrape()`:
   - Change from: `scrape(start=start_date, end=end_date, resume=resume, output=Path(output))`
   - Change to: `scrape(start=start_date, end=end_date, output=Path(output))`
5. Remove any logging references to `resume` parameter

**Verification**:
- Run `uv run ruff check src/dry_bridge/__main__.py`
- Run `uv run mypy src/dry_bridge/__main__.py`
- Run `uv run dry-bridge extract --help` and verify no `--resume` flag
- Simple, clear interface
- Run `uv run pytest` - all tests should still pass

---

## Task 7: Rewrite `refresh()` command in __main__.py

**Goal**: Replace timestamp-based logic with gap detection.

**Changes**:
1. Open `src/dry_bridge/__main__.py`
2. Add imports to the `from .load import (...)` line:
   - `find_missing_timestamps`
   - `group_by_date`
3. Add import: `from .scrape import scrape_client, scrape_date` (if not already present)
4. Replace the entire `refresh()` function body with:

```python
@app.command()
def refresh() -> None:
    """
    Fill any gaps in the database and add new data.
    
    Queries the database for missing 15-minute intervals, scrapes the
    necessary dates, and loads the missing data. This command automatically
    detects and fills gaps in historical data while also adding new records.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting refresh command")
    
    conn = database_connection()
    
    # Find all missing timestamps
    missing_timestamps = find_missing_timestamps(conn)
    
    if not missing_timestamps:
        logger.info("No missing data, database is complete!")
        return
    
    logger.info(f"Found {len(missing_timestamps)} missing timestamps")
    
    # Group by dates to scrape
    dates_to_scrape = group_by_date(missing_timestamps)
    logger.info(f"Need to scrape {len(dates_to_scrape)} dates to fill gaps")
    
    # Scrape the data
    client = scrape_client()
    all_results = []
    for date in dates_to_scrape:
        try:
            data = scrape_date(client, date)
            all_results.append(data)
        except Exception as e:
            logger.error(f"Failed to scrape {date}: {e}")
            # Continue with other dates
    
    # Process all scraped data
    all_raw_data = []
    for result in all_results:
        raw_data = flatten_raw_data(result)
        all_raw_data.extend(raw_data)
    
    # Filter to only the timestamps we're actually missing
    missing_set = set(missing_timestamps)
    filtered_raw = []
    for row in all_raw_data:
        if row.timestamp in missing_set:
            filtered_raw.append(row)
    
    logger.info(f"Loading {len(filtered_raw)} missing records")
    
    # Load raw data
    load_raw(conn, filtered_raw)
    conn.commit()
    
    # Transform and load processed data
    transformed_data = transform_raw_data(filtered_raw)
    transformed_data = list(set(transformed_data))  # dedupe
    transformed_data.sort(key=lambda x: x.timestamp)
    
    load_transformed(conn, transformed_data)
    conn.commit()
    
    logger.info(f"Refresh complete: filled {len(transformed_data)} gaps")
```

**Verification**:
- Run `uv run ruff check src/dry_bridge/__main__.py`
- Run `uv run mypy src/dry_bridge/__main__.py`
- Clear step-by-step logic
- Simple loops, no clever comprehensions
- Proper error handling with continue
- Run `uv run pytest` - all tests should still pass
- Imports added at same time as usage (no unused import warnings)

---

## Task 8: Update README.md to remove resume documentation

**Goal**: Update user documentation to reflect new behavior.

**Changes**:
1. Open `README.md`
2. Find the "Extracting Data" section
3. Remove example: `# Resume a previous extraction` and `dry-bridge extract --resume`
4. Update text to say: "Re-run the extract command to continue - it automatically skips existing files."
5. Find any other references to `--resume` flag and remove them
6. Add a "Migration Note" section (or add to existing):

```markdown
### Migration Note

If you have existing `metadata.json` files, they are no longer used and can be deleted.
The `--resume` flag has been removed - just re-run `extract` and it will automatically
skip any files that already exist.

The `refresh` command now automatically detects and fills gaps in the data.
```

**Verification**:
- Read through README for clarity
- No references to `--resume` remain
- Migration note is clear
- Run `uv run dry-bridge --help` to verify help text matches docs

---

## Task 9: Delete metadata.json from output directory

**Goal**: Clean up old metadata files.

**Changes**:
1. Check if `output/metadata.json` exists
2. If it exists, delete it: `rm output/metadata.json`
3. No code changes needed

**Verification**:
- Run `ls output/metadata.json` and confirm file not found
- Run `ls output/*.json | wc -l` to see remaining data files

---

## Task 10: Update function docstrings

**Goal**: Remove any remaining metadata references from docstrings.

**Changes**:
1. Search all files for "metadata" (case insensitive)
2. Check docstrings in:
   - `src/dry_bridge/__init__.py` - update module docstring if it mentions metadata
   - Any other files with metadata references
3. Update docstrings to remove metadata mentions

**Verification**:
- Run: `grep -ri "metadata" src/`
- Should only find references in comments/logs, not in docstrings
- Run `uv run ruff check .`
- Run `uv run pytest` - all tests should pass

---

## Task 11: Manual testing - extract command

**Goal**: Verify extract command works without resume flag.

**Test Steps**:
1. Create a test output directory: `mkdir -p test_output`
2. Run: `uv run dry-bridge extract --start 2023-08-01 --end 2023-08-05 --output test_output`
3. Verify files created: `ls test_output/*.json`
4. Run same command again
5. Verify it skips existing files (check logs)
6. Clean up: `rm -rf test_output`

**Expected Results**:
- First run: Downloads 4 files (Aug 1-4)
- Second run: Logs "Skipping, file already exists" for all dates
- No errors or warnings
- No metadata.json file created

---

## Task 12: Manual testing - refresh command (if database available)

**Goal**: Verify refresh command detects and fills gaps.

**Test Steps** (requires test database):
1. Check current record count: Query `SELECT COUNT(*) FROM dry_bridge_solar_processed`
2. Run: `uv run dry-bridge refresh`
3. Check logs for:
   - "Found X missing timestamps"
   - "Need to scrape Y dates"
   - "Refresh complete: filled Z gaps"
4. Run again immediately
5. Should see: "No missing data, database is complete!"

**Expected Results**:
- Detects missing timestamps
- Scrapes only missing dates
- Loads only missing records
- Second run finds no gaps
- Simple, readable logs

---

## Task 13: Final verification

**Goal**: Ensure everything works end-to-end.

**Changes**:
None - final verification.

**Verification Checklist**:
- [ ] No `Metadata` class exists in codebase
- [ ] No `metadata.json` files in output directory
- [ ] `extract` command has no `--resume` flag
- [ ] `refresh` command uses gap detection
- [ ] All tests pass
- [ ] All linting passes
- [ ] README is updated
- [ ] Code is simpler and more readable
- [ ] Logging is clear and informative
- [ ] No clever tricks, just clear Python

**Final Commands**:
```bash
uv run pytest
uv run ruff check .
uv run mypy src/
uv run dry-bridge --help
```

All should succeed with no errors.

---

## Summary

These 13 tasks break down the plan into atomic, verifiable changes:

- **Task 1**: Add `group_by_date()` to `load.py` with tests for the grouping logic
- **Task 2**: Add `find_missing_timestamps()` to `load.py` with tests for timestamp generation logic
- **Tasks 3-5**: Remove `Metadata` class and simplify `scrape.py` (with tests after each)
- **Task 6**: Update `extract()` command in `__main__.py` (with tests)
- **Task 7**: Rewrite `refresh()` command with gap detection (imports added here, with tests)
- **Task 8**: Update README documentation
- **Task 9**: Delete old metadata files
- **Task 10**: Update function docstrings
- **Tasks 11-12**: Manual testing (extract and refresh commands)
- **Task 13**: Final verification

Each task is small enough to complete in one sitting. Tests focus on data transformation logic, not database operations (assume database works). Tasks are ordered to minimize broken states - new functions are added and tested before old ones are removed. Imports are added when they're used to avoid ruff warnings.
