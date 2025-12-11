# Plan: Simplify Fetch Logic by Removing Retry Tracking Table

## Problem

Current implementation has two issues:

1. **Wrong source of truth**: Checks `dry_bridge_solar_processed` table for gaps, but raw table shows what was actually fetched
2. **Unnecessary retry tracking**: `dry_bridge_fetch_attempts` table adds complexity with no benefit

The `dry_bridge_solar_raw` table is the true source of truth - it contains exactly what the API returned. If timestamps are missing from raw, we need to fetch them. If they're in raw but not processed, that's a transformation bug.

## Solution

1. **Check raw table for gaps** - modify `find_missing_timestamps()` to query `dry_bridge_solar_raw`
2. **Remove retry tracking** - delete `dry_bridge_fetch_attempts` table and all related code

## Changes to find_missing_timestamps()

Change query from `dry_bridge_solar_processed` to `dry_bridge_solar_raw`:

```python
# Old - wrong table
cursor.execute("""
    SELECT timestamp 
    FROM dry_bridge_solar_processed 
    ORDER BY timestamp
""")
existing_timestamps = {row[0] for row in cursor.fetchall()}

# New - correct table (raw = what was fetched)
cursor.execute("""
    SELECT DISTINCT timestamp 
    FROM dry_bridge_solar_raw 
    ORDER BY timestamp
""")

# Parse ISO strings to datetime
existing_timestamps = set()
for row in cursor.fetchall():
    try:
        ts = iso_to_local(row[0])
        existing_timestamps.add(ts)
    except Exception as e:
        logger.warning(f"Failed to parse timestamp {row[0]}: {e}")
```

## Implementation

### 1. Update find_missing_timestamps() in load.py
- Change query from `dry_bridge_solar_processed` to `dry_bridge_solar_raw`
- Parse ISO timestamp strings to datetime objects
- Update docstring

### 2. Remove retry table from load.py
- Delete `dry_bridge_fetch_attempts` from `init_database()`
- Delete `record_fetch_attempt()` function
- Delete `should_skip_date()` function

### 3. Simplify refresh() in __main__.py
- Remove imports: `record_fetch_attempt`, `should_skip_date`
- Remove `eligible_dates` filtering (was using `should_skip_date()`)
- Remove all `record_fetch_attempt()` calls
- Remove conditional commits (single commit at end)
- Update docstring

### 4. Update docs
- Remove MAX_FETCH_ATTEMPTS from env.example and README
- Note that fetch_attempts table can be dropped

### 5. Testing

**Empty database**:
- Delete all data from raw table
- Run `refresh`
- Should fetch all historical data

**Single gap**:
- Delete records from raw for one specific date
- Run `refresh`
- Should fill only that date's gaps

**Already complete**:
- Database has all data
- Run `refresh`
- Should report "No missing data"

**Transformation issue**:
- Data exists in raw but not in processed
- Run `refresh`
- Should NOT re-fetch (correct behavior)
- Indicates a transformation bug to investigate separately

## Benefits

- **Correct source of truth**: Raw table = what was fetched, processed = what was transformed
- **Simpler**: Remove ~70 lines of retry tracking code
- **Self-healing**: Every run fills all gaps, no artificial limits
- **Transparent**: Gaps in raw = need to fetch; gaps in processed but not raw = transformation bug


