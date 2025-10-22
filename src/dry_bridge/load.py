#!/usr/bin/env python3
from dataclasses import dataclass, asdict

from psycopg2 import connect, Error
from psycopg2.extensions import connection

from .transform import ProcessedRow, RawRow


@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str


def database_connection(db_config: DatabaseConfig) -> connection:
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
    cursor = conn.cursor()

    # NOTE(@broarr): when inserting raw data we want to error on duplicates
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
    cursor = conn.cursor()

    # TODO(@broarr): do we really wanna overwrite like this?
    cursor.execute(
        """
        INSERT INTO dry_bridge_solar_processed 
        (timestamp, kw, kwh, mmbtu, mtco2e)
        VALUES (%(timestamp)s, %(kw)s, %(kwh)s, %(mmbtu)s, %(mtco2e)s);
        """,
        # ON CONFLICT (timestamp)
        # DO UPDATE SET
        #     kw = EXCLUDED.kw,
        #     kwh = EXCLUDED.kwh,
        #     mmbtu = EXCLUDED.mmbtu,
        #     mtco2e = EXCLUDED.mtco2e;
        asdict(processed_row),
    )

    cursor.close()


def load_raw(
    conn: connection,
    data: list[RawRow],
) -> None:
    try:
        for row in data:
            insert_raw_row(conn, row)
    except Error as error:
        conn.rollback()
        raise error


def load_transformed(conn: connection, data: list[ProcessedRow]):
    try:
        for row in data:
            insert_processed_row(conn, row)
    except Error as error:
        conn.rollback()
        raise error
