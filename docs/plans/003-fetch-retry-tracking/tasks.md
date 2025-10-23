# Tasks: Fetch Retry Tracking Implementation

## Phase 1: Database Schema
- [ ] Add `dry_bridge_fetch_attempts` table to `create_tables()` in `src/dry_bridge/load.py`
  - Three columns: `date DATE PRIMARY KEY`, `attempt_count INTEGER NOT NULL DEFAULT 1`, `status TEXT NOT NULL`
  - Add CHECK constraint for status values: 'empty', 'error', 'success'

## Phase 2: Configuration
- [ ] Add `MAX_FETCH_ATTEMPTS` constant to `src/dry_bridge/utils.py`
  - Read from env var with default value of 5
  - Add proper import: `import os` (if not present)

## Phase 3: Tracking Functions
- [ ] Add `record_fetch_attempt()` function to `src/dry_bridge/load.py`
  - Function signature: `record_fetch_attempt(conn: connection, date: datetime, status: str) -> None`
  - Use INSERT...ON CONFLICT DO UPDATE (upsert)
  - Increment attempt_count, update status
  - Add docstring
  - Add type hints
  - Use try/finally for cursor cleanup

- [ ] Add `should_skip_date()` function to `src/dry_bridge/load.py`
  - Function signature: `should_skip_date(conn: connection, date: datetime) -> bool`
  - Query tracking table for date
  - Return True if status='success' or count >= MAX_FETCH_ATTEMPTS
  - Return False for first attempt (no record)
  - Add docstring
  - Add type hints
  - Use try/finally for cursor cleanup
  - Import MAX_FETCH_ATTEMPTS from .utils

## Phase 4: Refresh Integration
- [ ] Modify `refresh()` function in `src/dry_bridge/__main__.py`
  - Add import: `from .load import record_fetch_attempt, should_skip_date`
  - After `group_by_date()`, filter dates using list comprehension with `should_skip_date()`
  - Log skipped count if > 0
  - In scrape loop after `scrape_date()`: check if `len(data["data"]) == 0` for empty result
    - If empty: call `record_fetch_attempt(conn, date, 'empty')`, `conn.commit()`, and skip to next date (don't append to all_results)
    - If has data: append to `all_results` as currently done, then immediately call `record_fetch_attempt(conn, date, 'success')` and `conn.commit()`
  - In exception handler: call `record_fetch_attempt(conn, date, 'error')` and `conn.commit()`

## Phase 5: Documentation
- [ ] Update `env.example`
  - Add `MAX_FETCH_ATTEMPTS=5` with comment explaining purpose

- [ ] Update `README.md`
  - Add MAX_FETCH_ATTEMPTS to Configuration section
  - Add brief explanation of retry tracking to refresh command description
  - Document new database table in Database Schema section (if exists)

## Phase 6: Testing
- [ ] Run `uv run ruff check .` - verify no linting errors
- [ ] Run `uv run mypy src/` - verify type checking passes
- [ ] Run `uv run pytest` - verify existing tests pass
- [ ] Manual test: Run refresh command multiple times
  - Verify tracking table created automatically
  - Verify dates recorded with correct status
  - Verify dates with repeated failures eventually skipped
  - Query: `SELECT * FROM dry_bridge_fetch_attempts ORDER BY date;`

## Notes
- Keep changes minimal and surgical
- Follow constitution: simple, explicit code with proper logging
- Add DEBUG logging in `should_skip_date()` for visibility
- Commit after each `record_fetch_attempt()` to persist tracking even if process crashes
- Total expected: ~60-80 lines of new code
