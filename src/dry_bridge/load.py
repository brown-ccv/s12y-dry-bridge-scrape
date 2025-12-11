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
from .utils import START_OF_OPERATION, round_down_15min, local_now, iso_to_local


logger = logging.getLogger(__name__)


class LoggingConnection(DefaultLoggingConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initialize(logger)


class LoggingCursor(DefaultLoggingCursor):
    def execute(self, sql, args=None):
        logger.debug(self.mogrify(sql, args))
        super().execute(sql, args)


def database_connection(verbose=False) -> connection:
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
        connection_factory=LoggingConnection if verbose else None,
    )
    logger.info("Database connection established successfully")
    create_tables(conn)
    return conn


def database_cursor(conn: connection, verbose=False) -> cursor:
    """
    Create a new database cursor.

    Creates a new database cursor using the provided connection.
    Ensures that the cursor logs the SQL queries for debugging

    Returns:
        cursor: PostgreSQL cursor object
    """
    return conn.cursor(cursor_factory=LoggingCursor if verbose else None)


def create_tables(conn: connection) -> None:
    """
    Create the required database tables if they don't exist.

    Creates two tables:
    - dry_bridge_solar_processed: For processed/calculated solar metrics
    - dry_bridge_solar_raw: For raw data from the monitoring system

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
        timestamps: List of timezone-aware datetime objects

    Returns:
        List of timezone-aware datetime objects representing unique dates at midnight
    """
    if not timestamps:
        return []
    
    # Get timezone from first timestamp (all should be same zone)
    tz = timestamps[0].tzinfo
    
    unique_dates = set()
    for ts in timestamps:
        unique_dates.add(ts.date())

    result = []
    for date in sorted(unique_dates):
        result.append(datetime.combine(date, datetime.min.time(), tzinfo=tz))

    return result


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


def find_missing_timestamps(conn: connection) -> list[datetime]:
    """
    Find all 15-minute intervals missing from the RAW data table.

    The raw table is the source of truth for what's been fetched from the API.
    Queries the database for existing timestamps and compares against
    expected intervals from START_OF_OPERATION to now.

    Args:
        conn: Active database connection

    Returns:
        List of missing datetime objects
    """
    logger.debug("Querying for missing timestamps in raw data")
    cursor = database_cursor(conn)

    cursor.execute("""
        SELECT DISTINCT timestamp 
        FROM dry_bridge_solar_raw 
        ORDER BY timestamp
    """)

    existing_timestamps = set()
    for row in cursor.fetchall():
        try:
            ts = iso_to_local(row[0])
            existing_timestamps.add(ts)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp {row[0]}: {e}")

    missing = compute_missing_timestamps(
        existing_timestamps, START_OF_OPERATION, round_down_15min(local_now())
    )

    logger.info(f"Found {len(missing)} missing timestamps in raw data")
    return missing
