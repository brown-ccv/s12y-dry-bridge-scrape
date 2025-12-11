"""
Main CLI application for the Dry Bridge Solar Data ETL pipeline.

This module provides command-line interface for extracting solar production data
from the Dry Bridge solar farm dashboard and loading it into a PostgreSQL database.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer
from dotenv import load_dotenv
from typing_extensions import Annotated

from .load import (
    database_connection,
    database_cursor,
    find_missing_timestamps,
    group_by_date,
    load_raw,
    load_transformed,
)
from .scrape import scrape, scrape_client, scrape_date
from .transform import flatten_raw_data, transform_raw_data
from .utils import START_OF_OPERATION, iso_to_local, local_now, remove_future_timestamps


app = typer.Typer()

load_dotenv()


logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

# Silence noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx_retries").setLevel(logging.WARNING)


@app.command()
def extract(
    start: Annotated[str, typer.Argument(help="start time for web scrape")] = "all",
    end: Annotated[str, typer.Argument(help="end time for web scrape")] = "now",
    output: Annotated[str, typer.Argument(help="output directory")] = "./output",
) -> None:
    """
    Extract solar production data from the web dashboard.

    One-time extraction for historical data import. Re-run to resume -
    automatically skips existing files.

    Downloads raw JSON data from the Dry Bridge solar farm dashboard for the specified
    date range. Data is saved as individual JSON files per day in the output directory.

    Args:
        start: Start date in ISO format (YYYY-MM-DD) or "all" for full history
        end: End date in ISO format (YYYY-MM-DD) or "now" for current date
        output: Directory to save the extracted JSON files
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting extract command: start={start}, end={end}, output={output}")

    tz = ZoneInfo("America/New_York")
    start_date = START_OF_OPERATION
    if start != "all":
        start_date = datetime.fromisoformat(start).replace(tzinfo=tz)
        logger.debug(f"Parsed start date: {start_date}")

    end_date = datetime.now(tz)
    if end != "now":
        end_date = datetime.fromisoformat(end).replace(tzinfo=tz)
        logger.debug(f"Parsed end date: {end_date}")

    scrape(start=start_date, end=end_date, output=Path(output))


@app.command()
def load(
    output: Annotated[
        str, typer.Argument(help="output directory containing dumps")
    ] = "./output",
    raw: Annotated[bool, typer.Option(help="load raw data")] = True,
    transform: Annotated[bool, typer.Option(help="load transformed data")] = True,
) -> None:
    """
    Load extracted data from scratch (clears existing data first).

    Processes JSON files one at a time to minimize memory usage. This command
    is for initial historical loads - it truncates the processed table before loading.
    Use 'refresh' command for ongoing updates.

    Args:
        output: Directory containing the extracted JSON files
        raw: Whether to load raw data into dry_bridge_solar_raw table
        transform: Whether to load transformed data into dry_bridge_solar_processed table

    Raises:
        Exception: If database configuration is invalid or missing from environment
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting load: output={output}, raw={raw}, transform={transform}")

    conn = database_connection()
    output_path = Path(output)

    # Clear tables - load is for initial historical loads only
    if raw:
        logger.info("Clearing raw table for fresh load")
        cursor = database_cursor(conn)
        cursor.execute("TRUNCATE dry_bridge_solar_raw")
        cursor.close()
        conn.commit()

    if transform:
        logger.info("Clearing processed table for fresh load")
        cursor = database_cursor(conn)
        cursor.execute("TRUNCATE dry_bridge_solar_processed")
        cursor.close()
        conn.commit()

    json_files = sorted(output_path.glob("*.json"))
    total_files = len(json_files)
    logger.info(f"Found {total_files} JSON files to process")

    if total_files == 0:
        logger.warning(f"No JSON files found in {output}")
        return

    total_raw_loaded = 0
    total_transformed_loaded = 0

    for i, file_path in enumerate(json_files, 1):
        if i % 10 == 0:
            logger.info(f"Progress: {i}/{total_files} files processed")

        try:
            data = json.loads(file_path.read_text())
        except Exception as e:
            logger.error(f"Failed to read {file_path.name}: {e}")
            continue

        raw_rows = flatten_raw_data(data)

        # Raw table: just insert (no constraints, duplicates OK)
        if raw:
            load_raw(conn, raw_rows)
            total_raw_loaded += len(raw_rows)

        # Processed table: simple insert (table is empty)
        if transform:
            transformed = transform_raw_data(raw_rows)
            transformed = list(set(transformed))
            transformed.sort(key=lambda x: x.timestamp)
            load_transformed(conn, transformed)
            total_transformed_loaded += len(transformed)

    conn.commit()

    logger.info(
        f"Load complete: {total_files} files processed. "
        f"Raw: {total_raw_loaded} rows. "
        f"Processed: {total_transformed_loaded} rows."
    )


@app.command()
def refresh() -> None:
    """
    Fill any gaps in the database and add new data.

    Queries the RAW data table for missing 15-minute intervals and scrapes
    the necessary dates to fill them. This command automatically detects and
    fills gaps in historical data while also adding new records.

    If a scrape fails, the gaps remain and will be retried on the next run.
    There are no retry limits.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting refresh command")

    conn = database_connection()

    missing_timestamps = find_missing_timestamps(conn)

    if not missing_timestamps:
        logger.info("No missing data, database is complete!")
        return

    # NOTE(@broarr): The api returns nulls for anything that's in the future
    #   we need to make sure to ignore those timestamps so we don't add nulls
    #   all over the database
    missing_timestamps = remove_future_timestamps(local_now(), missing_timestamps)

    # NOTE(@broarr): Sets compare faster than lists when filtering
    missing_set = set(missing_timestamps)

    logger.info(f"Found {len(missing_timestamps)} missing timestamps")

    dates_to_scrape = group_by_date(missing_timestamps)
    logger.info(f"Need to scrape {len(dates_to_scrape)} dates to fill gaps")

    client = scrape_client()
    total_loaded = 0
    total_dates = len(dates_to_scrape)

    for i, date in enumerate(dates_to_scrape, 1):
        if i % 10 == 0:
            logger.info(f"Progress: {i}/{total_dates} dates processed")

        try:
            data = scrape_date(client, date)
            if len(data["data"]) == 0:
                logger.warning(f"✗ {date.date()}: no data available")
                continue

            # Process this date immediately
            raw_data = flatten_raw_data(data)

            # Filter to only missing timestamps for this date
            filtered_raw = [
                row for row in raw_data if iso_to_local(row.timestamp) in missing_set
            ]

            if not filtered_raw:
                logger.debug(f"{date.date()}: no missing timestamps in this date")
                continue

            # Load raw data
            load_raw(conn, filtered_raw)

            # Transform and load processed data
            transformed = transform_raw_data(filtered_raw)
            transformed = list(set(transformed))
            transformed.sort(key=lambda x: x.timestamp)
            load_transformed(conn, transformed)

            total_loaded += len(transformed)

        except Exception as e:
            logger.error(f"Failed to scrape {date}: {e}")

    conn.commit()

    logger.info(f"Refresh complete: filled {total_loaded} gaps")


def main() -> None:
    """
    Entry point for the CLI application.

    This function is called when the package is executed as a script.
    It initializes the Typer application and handles command-line arguments.
    """
    app()
