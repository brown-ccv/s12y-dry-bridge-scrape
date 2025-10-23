#!/usr/bin/env python3
"""
Database loading module for solar production data.

This module handles all database operations including connection management,
table creation, and data insertion for both raw and processed solar data.
It uses PostgreSQL as the backend database with psycopg2 for connectivity.
"""

import logging
import os
from dataclasses import dataclass, asdict

from psycopg2 import connect, Error
from psycopg2.extensions import connection

from .transform import ProcessedRow, RawRow


logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """
    Database connection configuration.

    Contains all necessary parameters for establishing a PostgreSQL connection.
    """

    host: str  # Database server hostname or IP address
    port: int  # Database server port (typically 5432 for PostgreSQL)
    database: str  # Name of the database to connect to
    user: str  # Database username for authentication
    password: str  # Database password for authentication


def database_connection() -> connection:
    """
    Establish a database connection and ensure tables exist.

    Creates a PostgreSQL connection using the provided configuration and
    automatically creates the required tables if they don't exist.

    Args:
        db_config: Database connection configuration

    Returns:
        connection: PostgreSQL connection object

    Raises:
        Exception: If connection fails or table creation fails
    """
    logger.debug("Loading database configuration from environment")
    try:
        db_config = DatabaseConfig(
            host=os.environ["DB_HOST"],
            port=int(os.environ["DB_PORT"]),
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )
        logger.debug(
            f"Database config: {db_config.host}:{db_config.port}/{db_config.database} as {db_config.user}"
        )
    except KeyError as e:
        logger.error(f"Missing database environment variable: {e}")
        raise Exception("invalid database configuration, double check your environment")

    try:
        logger.info(
            f"Connecting to database: {db_config.host}:{db_config.port}/{db_config.database}"
        )
        connection = connect(
            host=db_config.host,
            port=db_config.port,
            database=db_config.database,
            user=db_config.user,
            password=db_config.password,
        )
        logger.info("Database connection established successfully")
        create_tables(connection)
        return connection
    except Error as e:
        logger.error(f"Database connection failed: {e}")
        raise Exception(f"error connecting to database: {e}")


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
        cursor = conn.cursor()

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


def insert_raw_row(conn: connection, raw_row: RawRow) -> None:
    """
    Insert a single raw data row into the database.

    Args:
        conn: Active database connection
        raw_row: Raw data row to insert
    """
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO dry_bridge_solar_raw
        (timestamp, name, type, units, value)
        VALUES (%(timestamp)s, %(name)s, %(type)s, %(units)s, %(value)s)
        """,
        asdict(raw_row),
    )

    cursor.close()


def insert_processed_row(conn: connection, processed_row: ProcessedRow) -> None:
    """
    Insert a single processed data row into the database.

    Args:
        conn: Active database connection
        processed_row: Processed data row to insert
    """
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO dry_bridge_solar_processed 
        (timestamp, kw, kwh, mmbtu, mtco2e)
        VALUES (%(timestamp)s, %(kw)s, %(kwh)s, %(mmbtu)s, %(mtco2e)s);
        """,
        asdict(processed_row),
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
        for i, row in enumerate(data):
            if i % 1000 == 0:
                logger.debug(f"Inserted {i}/{len(data)} raw rows")
            insert_raw_row(conn, row)
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
        for i, row in enumerate(data):
            if i % 1000 == 0:
                logger.debug(f"Inserted {i}/{len(data)} processed rows")
            insert_processed_row(conn, row)
        logger.info(f"Successfully loaded {len(data)} processed data rows")
    except Error as error:
        logger.error(f"Failed to load processed data: {error}")
        conn.rollback()
        raise error


def most_recent_record(conn: connection) -> ProcessedRow | None:
    logger.debug("Querying for most recent processed record")
    cursor = conn.cursor()

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
