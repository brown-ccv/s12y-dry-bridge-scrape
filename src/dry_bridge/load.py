#!/usr/bin/env python3
"""
Database loading module for solar production data.

This module handles all database operations including connection management,
table creation, and data insertion for both raw and processed solar data.
It uses PostgreSQL as the backend database with psycopg2 for connectivity.
"""

from dataclasses import dataclass, asdict

from psycopg2 import connect, Error
from psycopg2.extensions import connection

from .transform import ProcessedRow, RawRow


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


def database_connection(db_config: DatabaseConfig) -> connection:
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
    try:
        connection = connect(
            host=db_config.host,
            port=db_config.port,
            database=db_config.database,
            user=db_config.user,
            password=db_config.password,
        )
        create_tables(connection)
        return connection
    except Error as e:
        raise Exception(f"error connecting to database: {e}")


def create_tables(conn: connection):
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
    except Error as e:
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
    try:
        for row in data:
            insert_raw_row(conn, row)
    except Error as error:
        conn.rollback()
        raise error


def load_transformed(conn: connection, data: list[ProcessedRow]):
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
    try:
        for row in data:
            insert_processed_row(conn, row)
    except Error as error:
        conn.rollback()
        raise error
