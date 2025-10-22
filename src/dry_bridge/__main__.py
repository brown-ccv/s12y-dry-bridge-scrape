"""
Main CLI application for the Dry Bridge Solar Data ETL pipeline.

This module provides command-line interface for extracting solar production data
from the Dry Bridge solar farm dashboard and loading it into a PostgreSQL database.
"""

import logging
from datetime import datetime, timedelta
from itertools import chain
from pathlib import Path

import typer
from dotenv import load_dotenv
from typing_extensions import Annotated

from .load import (
    database_connection,
    load_raw,
    load_transformed,
    most_recent_record,
)
from .scrape import scrape, read_scrape, scrape_date
from .transform import flatten_raw_data, transform_raw_data
from .utils import START_OF_OPERATION, days_from_timestamp, round_down_15min, local_now


app = typer.Typer()

load_dotenv()


logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.CRITICAL,
)


@app.command()
def extract(
    start: Annotated[str, typer.Argument(help="start time for web scrape")] = "all",
    end: Annotated[str, typer.Argument(help="end time for web scrape")] = "now",
    resume: Annotated[bool, typer.Option(help="resume previous scrape")] = False,
    output: Annotated[str, typer.Argument(help="output directory")] = "./output",
) -> None:
    """
    Extract solar production data from the web dashboard.

    Downloads raw JSON data from the Dry Bridge solar farm dashboard for the specified
    date range. Data is saved as individual JSON files per day in the output directory.

    Args:
        start: Start date in ISO format (YYYY-MM-DD) or "all" for full history
        end: End date in ISO format (YYYY-MM-DD) or "now" for current date
        resume: Whether to resume from the last successful download
        output: Directory to save the extracted JSON files
    """
    start_date = START_OF_OPERATION
    if start != "all":
        start_date = datetime.fromisoformat(start)

    end_date = datetime.now()
    if end != "now":
        end_date = datetime.fromisoformat(end)

    scrape(start=start_date, end=end_date, resume=resume, output=Path(output))


@app.command()
def load(
    output: Annotated[
        str, typer.Argument(help="output directory containing dumps")
    ] = "./output",
    raw: Annotated[bool, typer.Option(help="load raw data")] = True,
    transform: Annotated[bool, typer.Option(help="load transformed data")] = True,
) -> None:
    """
    Load extracted data into PostgreSQL database.

    Reads JSON files from the output directory and loads them into the database.
    Can load both raw data and transformed/processed data based on the flags.

    Args:
        output: Directory containing the extracted JSON files
        raw: Whether to load raw data into dry_bridge_solar_raw table
        transform: Whether to load transformed data into dry_bridge_solar_processed table

    Raises:
        Exception: If database configuration is invalid or missing from environment
    """
    conn = database_connection()
    data = read_scrape(Path(output))
    raw_data = list(chain.from_iterable([flatten_raw_data(d) for d in data]))

    if raw:
        load_raw(conn, raw_data)
        conn.commit()

    if transform:
        # NOTE(@broarr): We dedup the records because of what appears to be a firmware
        #   bug in the solar farm sensors. Daylight savings is accounted for at the wrong
        #   time. Simply converting to UTC does not fix the problem, but luckily for us
        #   the data for the inverters is all 0 so it doesn't really matter much
        transformed_data = sorted(
            list(set(transform_raw_data(raw_data))), key=lambda x: x.timestamp
        )
        load_transformed(conn, transformed_data)
        conn.commit()


@app.command()
def refresh() -> None:
    conn = database_connection()

    row = most_recent_record(conn)
    timestamp = row.timestamp if row else START_OF_OPERATION
    missing_dates = days_from_timestamp(timestamp)
    results = [scrape_date(d) for d in missing_dates]
    raw_data = list(chain.from_iterable([flatten_raw_data(d) for d in results]))

    delta = timedelta(minutes=15)
    current_timestamp = timestamp + delta
    last_available_timestamp = round_down_15min(local_now())
    raw_rows = []
    while current_timestamp <= last_available_timestamp:
        found = False
        for raw_row in raw_data:
            if raw_row.timestamp == current_timestamp:
                found = True
                raw_rows.append(raw_row)
        if not found:
            print("did not find record for '{current_timestamp}'")

    load_raw(conn, raw_rows)
    conn.commit()

    transformed_data = sorted(
        list(set(transform_raw_data(raw_rows))), key=lambda x: x.timestamp
    )
    load_transformed(conn, transformed_data)
    conn.commit()


def main() -> None:
    """
    Entry point for the CLI application.

    This function is called when the package is executed as a script.
    It initializes the Typer application and handles command-line arguments.
    """
    app()
