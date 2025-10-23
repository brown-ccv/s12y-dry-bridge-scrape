# Plan: Fetch Retry Tracking System

## Problem

The `refresh` command repeatedly attempts to fetch dates that consistently return no data or fail with errors, wasting API calls and time.

## Solution

Add a simple database table to track fetch attempts per date and skip dates that have been tried too many times without success.

## Goals

1. Track fetch attempts per date in database
2. Skip dates after MAX_FETCH_ATTEMPTS failures
3. Never retry dates that succeeded

## Implementation

### 1. Database Schema

Add to `create_tables()` in `load.py`:

```sql
CREATE TABLE IF NOT EXISTS dry_bridge_fetch_attempts (
    date DATE PRIMARY KEY,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK (status IN ('empty', 'error', 'success'))
);
```

**Fields:**
- `date`: The date being scraped (PRIMARY KEY)
- `attempt_count`: Number of fetch attempts
- `status`: 'empty' (no data), 'error' (failed), or 'success' (got data)

### 2. Configuration

Add to `utils.py`:

```python
MAX_FETCH_ATTEMPTS = int(os.getenv("MAX_FETCH_ATTEMPTS", "5"))
```

Default of 5 attempts is reasonable for transient issues.

### 3. Tracking Functions

Add to `load.py`:

**`record_fetch_attempt(conn, date, status)`**

```python
def record_fetch_attempt(conn: connection, date: datetime, status: str) -> None:
    """Record or update fetch attempt for a date."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO dry_bridge_fetch_attempts (date, attempt_count, status)
            VALUES (%s, 1, %s)
            ON CONFLICT (date) DO UPDATE SET
                attempt_count = dry_bridge_fetch_attempts.attempt_count + 1,
                status = EXCLUDED.status
            """,
            (date.date(), status)
        )
    finally:
        cursor.close()
```

**`should_skip_date(conn, date) -> bool`**

```python
def should_skip_date(conn: connection, date: datetime) -> bool:
    """Check if date should be skipped due to retry limits."""
    from .utils import MAX_FETCH_ATTEMPTS
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT attempt_count, status 
            FROM dry_bridge_fetch_attempts 
            WHERE date = %s
            """,
            (date.date(),)
        )
        row = cursor.fetchone()
        
        if not row:
            return False  # First attempt
        
        count, status = row
        
        if status == 'success':
            return True  # Already got data
        
        if count >= MAX_FETCH_ATTEMPTS:
            return True  # Too many failures
        
        return False
    finally:
        cursor.close()
```

### 4. Integration with Refresh

Modify `refresh()` in `__main__.py`:

```python
def refresh(db_config: str = typer.Option(...)) -> None:
    conn = get_connection(db_config)
    missing = find_missing_timestamps(conn)
    if not missing:
        logger.info("No missing timestamps found")
        return
    
    dates_to_scrape = group_by_date(missing)
    logger.info(f"Need to scrape {len(dates_to_scrape)} dates")
    
    # Filter out dates that hit retry limits
    eligible_dates = [d for d in dates_to_scrape if not should_skip_date(conn, d)]
    skipped = len(dates_to_scrape) - len(eligible_dates)
    if skipped > 0:
        logger.info(f"Skipping {skipped} dates due to retry limits")
    
    for date in eligible_dates:
        try:
            raw_data = scrape_date(date)
            if not raw_data:
                logger.warning(f"✗ {date.date()}: no data available")
                record_fetch_attempt(conn, date, 'empty')
                conn.commit()
                continue
            
            logger.info(f"✓ {date.date()}: {len(raw_data)} data points")
            # ... process and load data
            record_fetch_attempt(conn, date, 'success')
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to scrape {date}: {e}")
            record_fetch_attempt(conn, date, 'error')
            conn.commit()
```

### 5. Documentation

Update `env.example`:
```bash
MAX_FETCH_ATTEMPTS=5  # Maximum retry attempts per date
```

Update `README.md`:
- Add MAX_FETCH_ATTEMPTS to configuration section
- Mention retry tracking in refresh command description

## Testing

Run refresh multiple times and verify:
1. First run: all dates attempted, recorded in table
2. Empty dates: stop after 5 attempts
3. Successful dates: never retried
4. Query tracking: `SELECT * FROM dry_bridge_fetch_attempts ORDER BY date;`

## Summary

~60-80 lines of code to add simple retry tracking. Table automatically created on first run. Dates with repeated failures (empty or error) stop after MAX_FETCH_ATTEMPTS. Successful dates never retried.
