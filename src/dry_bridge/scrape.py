"""
Web scraping module for extracting solar production data.

This module handles the extraction of solar production data from the Dry Bridge
solar farm dashboard. It manages authentication, retry logic, and data persistence
for reliable data collection across date ranges.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from httpx_retries import RetryTransport, Retry


logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
HOME_URL = "https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US"
API_URL = "https://hmi.alsoenergy.com/api/view/sourcedata/C44014"


@dataclass
class Metadata:
    """
    Metadata for tracking scraping progress and results.

    This class manages the state of data downloads, including tracking successful
    and failed downloads, and enabling resume functionality for interrupted scrapes.
    """

    path: Path  # Path to the metadata file on disk
    last_start: datetime | None  # The last successfully processed start date
    success: list[
        str
    ]  # List of successfully downloaded date strings (YYYY-MM-DD format)
    failed: list[str]  # List of failed download date strings (YYYY-MM-DD format)

    def save(self) -> None:
        """
        Save metadata to disk as JSON.

        Persists the current state of the scraping metadata to enable
        resuming interrupted scrapes and tracking download history.
        """
        logger.debug(f"Saving metadata to {self.path}")
        logger.debug(
            f"Success count: {len(self.success)}, Failed count: {len(self.failed)}"
        )
        with open(self.path, "w") as f:
            date_str = self.last_start.strftime("%Y-%m-%d") if self.last_start else None
            logger.debug(f"Last start date: {date_str}")
            f.write(
                json.dumps(
                    {
                        "last_start": date_str,
                        "success": self.success,
                        "failed": self.failed,
                    }
                )
            )

    @staticmethod
    def load(path: Path) -> "Metadata":
        """
        Load metadata from disk or create new instance if file doesn't exist.

        Args:
            path: Path to the metadata JSON file

        Returns:
            Metadata: Loaded metadata instance or new empty instance
        """
        logger.debug(f"Loading metadata from {path}")
        try:
            with open(path, "r") as f:
                j = json.loads(f.read())
                logger.debug(
                    f"Loaded metadata: last_start={j['last_start']}, success={len(j['success'])}, failed={len(j['failed'])}"
                )
                return Metadata(
                    last_start=j["last_start"],
                    success=j["success"],
                    failed=j["failed"],
                    path=path,
                )
        except FileNotFoundError:
            logger.info(f"Metadata file {path} not found, creating new metadata")
            return Metadata(last_start=None, success=[], failed=[], path=path)


def scrape(
    start: datetime,
    end: datetime,
    resume: bool,
    output: Path,
) -> None:
    """
    Main scraping orchestration function.

    Coordinates the scraping process by setting up output directories,
    loading metadata, and determining the appropriate date range based
    on resume functionality.

    Args:
        start: Start date for scraping
        end: End date for scraping
        resume: Whether to resume from last successful download
        output: Directory to save downloaded files
    """
    logger.info(
        f"Starting scrape from {start} to {end}, resume={resume}, output={output}"
    )

    if not output.exists():
        logger.info(f"Creating output directory: {output}")
        output.mkdir()

    metadata = Metadata.load(Path(output) / "metadata.json")
    last_start = metadata.last_start
    logger.debug(f"Last start from metadata: {last_start}")

    client = scrape_client()

    if start and resume and last_start:
        logger.info(f"Resuming from last start date: {last_start}")
        metadata = scrape_range(client, last_start, end, output, metadata)
    else:
        logger.info(f"Starting fresh scrape from: {start}")
        metadata = scrape_range(client, start, end, output, metadata)

    metadata.save()
    logger.info("Scrape completed and metadata saved")


def scrape_client() -> httpx.Client:
    retry = Retry(total=MAX_RETRIES, backoff_factor=0.5)
    client = httpx.Client(transport=RetryTransport(retry=retry))

    logger.debug(f"Getting auth cookies from: {HOME_URL}")
    # NOTE(@broarr): This is to get the auth cookies only
    result = client.get(HOME_URL, follow_redirects=True)
    logger.debug(f"Auth request status: {result.status_code}")

    return client


def scrape_date(client: httpx.Client, date: datetime) -> dict[str, Any]:
    logger.debug(f"Scraping data for date: {date}")

    date_str = date.strftime("%Y-%m-%d")
    logger.debug(f"Formatted date string: {date_str}")

    req_params = {
        "type": 0,
        "parameters": [
            {"name": "Context", "type": 3, "value": "site"},
            {"name": "Source", "type": 1, "value": "59449"},
            {"name": "Start", "type": 7, "value": date_str},
            {"name": "End", "type": 7, "value": date_str},
        ],
        "props": None,
        "series": [],
        "id": 15,
        "pollInterval": 5,
    }
    headers = {"Referer": HOME_URL}
    logger.debug(f"Making API request to: {API_URL}")
    logger.debug(f"Request parameters: {req_params}")

    result = client.post(API_URL, headers=headers, json=req_params, timeout=10.0)
    logger.debug(f"API request status: {result.status_code}")

    response_data = result.json()
    data_count = len(response_data.get("data", []))
    logger.debug(f"Received {data_count} data points for {date_str}")

    return response_data


def scrape_range(
    client: httpx.Client,
    start: datetime,
    end: datetime,
    output: Path,
    metadata: Metadata,
) -> Metadata:
    """
    Download solar data for each day in the specified date range.

    This function performs the actual HTTP requests to the solar dashboard API,
    handling authentication through cookies and managing retry logic for failed
    requests. Each day's data is saved as a separate JSON file.

    Args:
        start: Start date for the range
        end: End date for the range
        output: Directory to save JSON files
        metadata: Metadata object to track progress

    Returns:
        Metadata: Updated metadata with success/failure tracking
    """
    logger.info(f"Scraping range from {start} to {end}")
    current_date = start
    day_count = 0

    while current_date < end:
        metadata.last_start = current_date
        current_date += timedelta(days=1)
        day_count += 1

        date_str = current_date.strftime("%Y-%m-%d")
        logger.info(f"Processing day {day_count}: {date_str}")

        try:
            logger.debug(f"Calling scrape_date for {current_date}")
            data = scrape_date(client, current_date)
            print(data)

            if len(data["data"]) > 0:
                logger.info(
                    f"Successfully scraped {len(data['data'])} data points for {date_str}"
                )
                metadata.success.append(date_str)

                output_file = output / f"{date_str}.json"
                logger.debug(f"Writing data to file: {output_file}")

                with open(output_file, "w") as f:
                    f.write(json.dumps(data, indent=2, sort_keys=True))

                logger.debug(
                    f"Successfully wrote {output_file.stat().st_size} bytes to {output_file}"
                )
            else:
                error_msg = f"no data in response body for date {date_str}"
                logger.warning(f"✗ {error_msg}")
                raise Exception(error_msg)

        except (httpx.HTTPError, Exception) as e:
            logger.error(f"✗ Failed to scrape {date_str}: {e}")
            metadata.failed.append(date_str)

    logger.info(
        f"Completed scraping {day_count} days. Success: {len(metadata.success)}, Failed: {len(metadata.failed)}"
    )
    return metadata


def read_scrape(output: Path) -> list[dict[str, Any]]:
    """
    Read all scraped JSON files from the output directory.

    Loads and parses all JSON files (excluding metadata) from the specified
    directory, sorting them by date to ensure chronological processing.

    Args:
        output: Directory containing the scraped JSON files

    Returns:
        list[dict]: List of parsed JSON data from all files
    """
    logger.debug(f"Reading scraped files from {output}")
    data = []
    files = [f for f in output.glob("*.json") if "metadata" not in f.name]
    logger.info(f"Found {len(files)} JSON files to read")

    files = sorted(files, key=lambda f: datetime.fromisoformat(f.stem))
    logger.debug(f"Processing files in chronological order: {[f.name for f in files]}")

    for f in files:
        logger.debug(f"Reading file: {f}")
        data.append(read_scrape_file(f))

    logger.info(f"Successfully read {len(data)} data files")
    return data


def read_scrape_file(fname: Path) -> dict[str, Any]:
    """
    Read and parse a single scraped JSON file.

    Args:
        fname: Path to the JSON file to read

    Returns:
        dict: Parsed JSON data from the file
    """
    logger.debug(f"Reading scrape file: {fname}")
    try:
        data = json.loads(fname.read_text())
        logger.debug(
            f"Successfully parsed {fname}, data points: {len(data.get('data', []))}"
        )
        return data
    except Exception as e:
        logger.error(f"Failed to read/parse {fname}: {e}")
        raise
