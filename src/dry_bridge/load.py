#!/usr/bin/env python3
"""
Database loading module for solar production data.

This module handles all database operations including connection management,
table creation, and data insertion for both raw and processed solar data.
It uses PostgreSQL as the backend database with psycopg2 for connectivity.
"""

import logging
import os
from datetime import datetime, timedelta

from psycopg2 import connect, Error
from psycopg2.extensions import connection, cursor
from psycopg2.extras import (
    execute_values,
    LoggingConnection as DefaultLoggingConnection,
    LoggingCursor as DefaultLoggingCursor,
)

from .transform import ProcessedRow, RawRow
from .utils import START_OF_OPERATION, round_down_15min, local_now


logger = logging.getLogger(__name__)


class LoggingConnection(DefaultLoggingConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initialize(logger)


class LoggingCursor(DefaultLoggingCursor):
    def execute(self, sql, args=None):
        logger.debug(self.mogrify(sql, args))
        super().execute(sql, args)


def database_connection() -> connection:
    """
    Establish a database connection and ensure tables exist.

    Creates a PostgreSQL connection using environment variables and
    automatically creates the required tables if they don't exist.

    Returns:
        connection: PostgreSQL connection object

    Raises:
        KeyError: If required environment variable is missing
        psycopg2.Error: If connection fails
    """
    logger.debug("Loading database configuration from environment")
    host = os.environ["DB_HOST"]
    port = int(os.environ["DB_PORT"])
    database = os.environ["DB_NAME"]
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]

    logger.debug(f"Database config: {host}:{port}/{database} as {user}")
    logger.info(f"Connecting to database: {host}:{port}/{database}")

    conn = connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        connection_factory=LoggingConnection,
    )
    logger.info("Database connection established successfully")
    create_tables(conn)
    return conn


def database_cursor(conn: connection) -> cursor:
    """
    Create a new database cursor.

    Creates a new database cursor using the provided connection.
    Ensures that the cursor logs the SQL queries for debugging

    Returns:
        cursor: PostgreSQL cursor object
    """
    return conn.cursor(cursor_factory=LoggingCursor)


def create_tables(conn: connection) -> None:
    """
    Create the required database tables if they don't exist.

    Creates three tables:
    - dry_bridge_solar_processed: For processed/calculated solar metrics
    - dry_bridge_solar_raw: For raw data from the monitoring system
    - dry_bridge_fetch_attempts: For tracking scrape attempts and retry limits

    Args:
        conn: Active database connection

    Raises:
        Exception: If table creation fails
    """
    logger.debug("Creating database tables if they don't exist")
    try:
        cursor = database_cursor(conn)

        create_table_query = """
        CREATE TABLE IF NOT EXISTS dry_bridge_solar_processed (
            timestamp TIMESTAMP PRIMARY KEY,
            kw FLOAT,
            kwh FLOAT,
            mmbtu FLOAT,
            mtco2e FLOAT,
            UNIQUE (timestamp)
        );

        CREATE TABLE IF NOT EXISTS dry_bridge_solar_raw (
            timestamp TEXT,
            name TEXT,
            type TEXT,
            units TEXT,
            value FLOAT
        );

        CREATE TABLE IF NOT EXISTS dry_bridge_fetch_attempts (
            date DATE PRIMARY KEY,
            attempt_count INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL CHECK (status IN ('empty', 'error', 'success'))
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
        cursor.close()
        logger.debug("Database tables created successfully")
    except Error as e:
        logger.error(f"Failed to create tables: {e}")
        raise Exception(f"error creating tables: {e}")


def insert_raw_row(conn: connection, raw_rows: list[RawRow]) -> None:
    """
    Insert a single raw data row into the database.

    Args:
        conn: Active database connection
        raw_row: Raw data row to insert
    """
    cursor = database_cursor(conn)

    execute_values(
        cursor,
        """
        INSERT INTO dry_bridge_solar_raw
        (timestamp, name, type, units, value)
        VALUES %s
        """,
        [(x.timestamp, x.name, x.type, x.units, x.value) for x in raw_rows],
    )

    cursor.close()


def insert_processed_row(conn: connection, processed_rows: list[ProcessedRow]) -> None:
    """
    Insert a single processed data row into the database.

    Ignores duplicates since files may contain overlapping timestamps.

    Args:
        conn: Active database connection
        processed_row: Processed data row to insert
    """
    cursor = database_cursor(conn)

    execute_values(
        cursor,
        """
        INSERT INTO dry_bridge_solar_processed 
        (timestamp, kw, kwh, mmbtu, mtco2e)
        VALUES %s
        ON CONFLICT (timestamp) DO NOTHING
        """,
        [(x.timestamp, x.kw, x.kwh, x.mmbtu, x.mtco2e) for x in processed_rows],
    )

    cursor.close()


def load_raw(
    conn: connection,
    data: list[RawRow],
) -> None:
    """
    Load a list of raw data rows into the database.

    Inserts all rows in a single transaction, rolling back if any
    insertion fails to maintain data consistency.

    Args:
        conn: Active database connection
        data: List of raw data rows to insert

    Raises:
        Error: If any insertion fails, causing transaction rollback
    """
    logger.info(f"Loading {len(data)} raw data rows into database")
    try:
        insert_raw_row(conn, data)
        logger.info(f"Successfully loaded {len(data)} raw data rows")
    except Error as error:
        logger.error(f"Failed to load raw data: {error}")
        conn.rollback()
        raise error


def load_transformed(conn: connection, data: list[ProcessedRow]) -> None:
    """
    Load a list of processed data rows into the database.

    Inserts all rows in a single transaction, rolling back if any
    insertion fails to maintain data consistency.

    Args:
        conn: Active database connection
        data: List of processed data rows to insert

    Raises:
        Error: If any insertion fails, causing transaction rollback
    """
    logger.info(f"Loading {len(data)} processed data rows into database")
    try:
        insert_processed_row(conn, data)
        logger.info(f"Successfully loaded {len(data)} processed data rows")
    except Error as error:
        logger.error(f"Failed to load processed data: {error}")
        conn.rollback()
        raise error


def most_recent_record(conn: connection) -> ProcessedRow | None:
    logger.debug("Querying for most recent processed record")
    cursor = database_cursor(conn)

    try:
        cursor.execute(
            """
            SELECT * FROM dry_bridge_solar_processed
            ORDER BY timestamp DESC
            LIMIT 1;
            """
        )
        record = cursor.fetchone()

        if record is None:
            logger.info("No processed records found in database")
            return None

        logger.debug(f"Most recent record timestamp: {record[0]}")
        return ProcessedRow(
            timestamp=record[0],
            kw=record[1],
            kwh=record[2],
            mmbtu=record[3],
            mtco2e=record[4],
        )
    except Error as e:
        logger.error(f"Failed to query most recent record: {e}")
        conn.rollback()
        raise Error


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

    result = []
    for date in sorted(unique_dates):
        result.append(datetime.combine(date, datetime.min.time()))

    return result


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


def record_fetch_attempt(conn: connection, date: datetime, status: str) -> None:
    """Record or update fetch attempt for a date."""

    # NOTE(@broarr): This script is designed to run every 15 minutes. The
    #   current state of the fetch attempt accounting makes it so that
    #   refetches increment the counter, or set success. This prevents the
    #   real-time-ish update of the database. By exiting if the date to process
    #   is today we prevent that problem. Today is the only day that can be
    #   incrementally updated, so it should be safe
    if date.date() == local_now().date():
        logger.warn(f"Skipping fetch attempt for today, {date}")
        return

    cursor = database_cursor(conn)
    try:
        cursor.execute(
            """
            INSERT INTO dry_bridge_fetch_attempts (date, attempt_count, status)
            VALUES (%s, 1, %s)
            ON CONFLICT (date) DO UPDATE SET
                attempt_count = dry_bridge_fetch_attempts.attempt_count + 1,
                status = EXCLUDED.status
            """,
            (date.date(), status),
        )
    finally:
        cursor.close()


def should_skip_date(conn: connection, date: datetime) -> bool:
    """Check if date should be skipped due to retry limits."""
    from .utils import MAX_FETCH_ATTEMPTS

    date_only = date.date()
    cursor = database_cursor(conn)
    try:
        cursor.execute(
            """
            SELECT attempt_count, status 
            FROM dry_bridge_fetch_attempts 
            WHERE date = %s
            """,
            (date_only,),
        )
        row = cursor.fetchone()

        if not row:
            return False

        count, status = row

        if status == "success":
            logger.debug(f"{date_only}: Already successful, skipping")
            return True

        if count >= MAX_FETCH_ATTEMPTS:
            logger.debug(
                f"{date_only}: Hit max attempts ({count}/{MAX_FETCH_ATTEMPTS}), skipping"
            )
            return True

        return False
    finally:
        cursor.close()
