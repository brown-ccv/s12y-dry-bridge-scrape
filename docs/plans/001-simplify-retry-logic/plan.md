# Plan: Simplify Retry Logic Using Database as Source of Truth

## Current State Analysis

### Existing Complexity
The current implementation uses a `Metadata` class that tracks:
- `last_start`: The last successfully processed start date
- `success`: List of successfully downloaded date strings
- `failed`: List of failed download date strings
- Persisted as `metadata.json` in the output directory

**Problems:**
1. Metadata file can get out of sync with actual files on disk
2. Two sources of truth (metadata.json + actual JSON files)
3. Complexity in managing success/failed lists
4. Resume logic is convoluted (checks both `resume` flag and `last_start`)
5. Files are only used for one-time historical load, not ongoing operations

### Current Usage Pattern
- **Primary workflow**: `refresh` command runs regularly (cron/scheduled) - no files involved
- **One-time setup**: `extract` and `load` commands used once for historical data import
- **Files on disk**: Temporary artifacts, not the source of truth

### The Real Source of Truth
The `dry_bridge_solar_processed` table in PostgreSQL is the canonical record of what data exists.

## Proposed Simplified Approach

### Core Principle
**Use the database as the single source of truth.** Find gaps in timestamp sequences and fill them. No metadata, no file tracking needed.

### New Strategy

#### 1. **Simple Database Gap Detection**
Query the database to find all missing 15-minute intervals using plain Python:
- Data should have records every 15 minutes (00, 15, 30, 45 minutes past the hour)
- Find gaps between START_OF_OPERATION and current time
- Return list of missing timestamps to scrape

```python
def find_missing_timestamps(conn: connection) -> list[datetime]:
    """Find all 15-minute intervals missing from the database."""
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

Simple and readable - no complex SQL, just Python loops and sets.

#### 2. **Group Missing Timestamps by Date**
Convert missing timestamps into dates to scrape (since API works per-day):

```python
def group_by_date(timestamps: list[datetime]) -> list[datetime]:
    """Group timestamps into unique dates."""
    unique_dates = set()
    for ts in timestamps:
        unique_dates.add(ts.date())
    
    # Convert back to datetime objects for scraping
    result = []
    for date in sorted(unique_dates):
        result.append(datetime.combine(date, datetime.min.time()))
    
    return result
```

No fancy comprehensions - just clear loops.

#### 4. **Simplified Extract Command**
The `extract` command becomes even simpler - just scrape and save to files for one-time historical load:

```python
def scrape(start: datetime, end: datetime, output: Path) -> None:
    """Scrape date range and save to files (for historical data import only)."""
    logger.info(f"Extracting from {start} to {end}, output={output}")
    
    if not output.exists():
        output.mkdir()
    
    client = scrape_client()
    current_date = start
    
    while current_date < end:
        date_str = current_date.strftime("%Y-%m-%d")
        output_file = output / f"{date_str}.json"
        
        # Skip if already scraped
        if output_file.exists():
            logger.debug(f"Skipping {date_str}, already exists")
            current_date += timedelta(days=1)
            continue
        
        try:
            data = scrape_date(client, current_date)
            if len(data["data"]) > 0:
                with open(output_file, "w") as f:
                    json.dump(data, f, indent=2, sort_keys=True)
                logger.info(f"✓ {date_str}: {len(data['data'])} data points")
            else:
                logger.warning(f"✗ {date_str}: no data")
        except Exception as e:
            logger.error(f"✗ {date_str}: {e}")
        
        current_date += timedelta(days=1)
```

No resume flag needed - just re-run and it skips existing files.

#### 4. **Enhanced Refresh Command**
Make `refresh` smarter to fill gaps, not just append:

```python
def refresh() -> None:
    """Fill any gaps in the database and add new data."""
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
            # Continue with other dates - can retry on next refresh
    
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

Clear step-by-step logic with simple loops. If scraping fails for a date, it logs and continues - the gap will be detected and retried on the next refresh run.

#### 5. **Remove Metadata Completely**
Delete:
- `Metadata` dataclass (entire class ~90 lines)
- `metadata.json` file references
- `resume` parameter from `extract` command
- All success/failure list tracking

Keep:
- `most_recent_record()` function - useful for quick checks and debugging

## Implementation Steps

### Phase 1: Add Gap Detection to `load.py`
1. Add `find_missing_timestamps(conn)` function - simple Python loop approach
2. Add `group_by_date(timestamps)` helper function
3. Keep existing `most_recent_record()` function (useful for debugging)
4. Add these as new functions at the end of the file

### Phase 2: Refactor `scrape.py`
1. Remove entire `Metadata` class (~90 lines, lines 28-93)
2. Simplify `scrape()` function:
   - Remove `resume` parameter
   - Remove all metadata loading/saving
   - Just check if output files exist before scraping
3. Simplify `scrape_range()` function:
   - Remove metadata parameter
   - Remove success/failed tracking
   - Just scrape dates and save files
   - Log errors but continue
4. Keep `scrape_client()` unchanged
5. Keep `scrape_date()` signature unchanged (still takes client parameter)
6. Keep `read_scrape()` and `read_scrape_file()` unchanged

### Phase 3: Update `__main__.py`
1. **Update `extract()` command**:
   - Remove `resume` parameter from function signature
   - Update docstring: "One-time extraction for historical data import. Re-run to resume - automatically skips existing files."
   - Remove resume-related logic

2. **Update `refresh()` command**:
   - Replace current timestamp-based logic with gap detection
   - Use `find_missing_timestamps()` instead of `most_recent_record()`
   - Use `group_by_date()` to get dates to scrape
   - Filter scraped data to only missing timestamps
   - Add better error handling for scraping failures

3. **Keep `load()` command unchanged**

### Phase 4: Testing Strategy
Test scenarios to validate:

1. **Empty database**: 
   - Run `refresh` with empty database
   - Should scrape from START_OF_OPERATION to now
   
2. **Gap in the middle**:
   - Manually delete some records from middle of date range
   - Run `refresh`
   - Should only scrape the missing dates

3. **Gap at the end**:
   - Database current but missing last day
   - Run `refresh`
   - Should scrape only recent data

4. **Multiple gaps**:
   - Delete records from several different dates
   - Run `refresh`
   - Should fill all gaps

5. **Already complete**:
   - Database has all data
   - Run `refresh`
   - Should report "No missing data"

6. **Extract command**:
   - Run `extract` on empty output directory
   - Run again - should skip existing files
   - Verify files created correctly

### Phase 5: Cleanup and Documentation
1. Delete any existing `metadata.json` files from output directories
2. Update README.md:
   - Remove `--resume` flag documentation
   - Document that `extract` automatically skips existing files
   - Explain that database is source of truth for `refresh`
   - Note that `refresh` automatically fills gaps
   - Add migration note: "Old metadata.json files are no longer needed"
3. Update all docstrings to remove metadata references
4. Update function signatures to remove resume parameters

## Benefits of This Approach

1. **Database as Single Source of Truth**: PostgreSQL tracks what data exists, not files or metadata
2. **Gap-Aware**: Automatically finds and fills discontinuities in the data
3. **Self-Healing**: `refresh` command fills gaps and adds new data in one operation
4. **Simpler Code**: Remove ~90 lines of metadata management code
5. **Files are Transient**: Only used for one-time historical load via `extract`/`load`
6. **No Sync Issues**: Database can't get out of sync with itself
7. **Idempotent**: Can run `extract` or `refresh` multiple times safely
8. **No External Dependencies**: Pure Python loops and simple SQL SELECT queries
9. **Readable**: Clear step-by-step logic, no clever abstractions or complex SQL

## Edge Cases to Handle

1. **Empty Database**: 
   - `find_missing_timestamps()` will find all timestamps from START_OF_OPERATION
   - Works correctly

2. **Very Large Gaps**: 
   - If database has years of missing data, query could take time
   - Loading all timestamps into a Python set is fine (even millions of records)
   - Mitigate: Could add optional `lookback_days` parameter if needed later

3. **Partial Day Data**: 
   - If scraping fails mid-day, some timestamps saved, some not
   - Gap detection will find the missing timestamps
   - Next `refresh` will re-scrape that date and fill the gaps
   - Filtering by `missing_set` ensures we only load what's actually missing

4. **Scraping Failures**: 
   - If scraping fails for a date, log error and continue
   - Gap remains in database
   - Next `refresh` run will try again
   - No data loss - just delays backfill

5. **Timezone Handling**: 
   - Already handled by existing `local_now()` and `round_down_15min()` functions
   - Database stores UTC, comparison works correctly

6. **Duplicate Prevention**:
   - `dry_bridge_solar_processed` has PRIMARY KEY on timestamp
   - Database will reject duplicates
   - Current code already dedupes with `set()` before loading

7. **Corrupted Files**: 
   - Extract command: If output file exists but is corrupted, manually delete it
   - Rerun extract to re-scrape that date
   - This is a one-time operation so manual intervention is acceptable

## Migration Guide

### For Users
If you have existing `metadata.json` files:
1. They are no longer used and can be deleted
2. The `--resume` flag has been removed from `extract`
3. Just re-run `extract` if you need more historical data - it skips existing files automatically
4. Run `refresh` to fill any gaps and get latest data

### Breaking Changes
- `extract` command no longer accepts `--resume` flag
- `metadata.json` files are ignored
- Behavior change: `extract` is now always idempotent (always skips existing files)

### What Stays the Same
- File format: `YYYY-MM-DD.json` unchanged
- Database schema: unchanged
- `load` command: unchanged  
- `refresh` command: same usage, but smarter internally

## Code Complexity Comparison

**Before:**
- Metadata class with save/load logic: ~90 lines
- Resume logic checking both metadata and flags: ~15 lines
- Success/failure list management: scattered throughout
- Manual timestamp checking in refresh: ~20 lines

**After:**
- Gap detection function: ~20 lines
- Group by date function: ~10 lines
- Simplified scrape logic: ~30 lines
- Smarter refresh logic: ~40 lines

**Net reduction**: ~30 lines removed, plus much clearer logic

## Summary

This refactor simplifies the codebase by using the database as the single source of truth for what data has been extracted. The `refresh` command becomes gap-aware, automatically filling discontinuities in the data. The `extract` command becomes simpler - just scrape dates and skip files that exist. No complex metadata tracking, no sync issues, and the code becomes more maintainable and easier to understand.

The implementation uses simple Python loops and basic SQL queries - no clever abstractions, no complex window functions, just clear step-by-step logic that's easy to read and debug.
