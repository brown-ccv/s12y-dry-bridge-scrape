"""
Web scraping module for extracting solar production data.

This module handles the extraction of solar production data from the Dry Bridge
solar farm dashboard. It manages authentication, retry logic, and data persistence
for reliable data collection across date ranges.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from httpx_retries import RetryTransport, Retry


logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
HOME_URL = "https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US"
API_URL = "https://hmi.alsoenergy.com/api/view/sourcedata/C44014"


def scrape(
    start: datetime,
    end: datetime,
    output: Path,
) -> None:
    """
    Scrape date range and save to files.

    This is a one-time operation for historical data import. Re-run to
    resume - it automatically skips existing files.

    Args:
        start: Start date for scraping
        end: End date for scraping
        output: Directory to save downloaded files
    """
    logger.info(f"Scraping from {start} to {end}, output={output}")

    if not output.exists():
        logger.info(f"Creating output directory: {output}")
        output.mkdir()

    client = scrape_client()
    scrape_range(client, start, end, output)

    logger.info("Scrape completed")


def scrape_client() -> httpx.Client:
    retry = Retry(total=MAX_RETRIES, backoff_factor=0.5)
    client = httpx.Client(
        transport=RetryTransport(retry=retry), verify=False, timeout=25.0
    )

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
) -> None:
    """
    Download solar data for each day in the specified date range.

    This function performs the actual HTTP requests to the solar dashboard API,
    handling authentication through cookies. Each day's data is saved as a
    separate JSON file.

    Args:
        client: HTTP client with authentication cookies
        start: Start date for the range
        end: End date for the range
        output: Directory to save JSON files
    """
    logger.info(f"Scraping range from {start} to {end}")
    current_date = start
    day_count = 0

    while current_date < end:
        current_date += timedelta(days=1)
        day_count += 1

        date_str = current_date.strftime("%Y-%m-%d")
        output_file = output / f"{date_str}.json"

        if output_file.exists():
            logger.debug(f"Skipping {date_str}, file already exists")
            continue

        logger.info(f"Processing day {day_count}: {date_str}")

        try:
            data = scrape_date(client, current_date)

            if len(data["data"]) > 0:
                logger.info(
                    f"Successfully scraped {len(data['data'])} data points for {date_str}"
                )

                with open(output_file, "w") as f:
                    f.write(json.dumps(data, indent=2, sort_keys=True))

                logger.debug(
                    f"Wrote {output_file.stat().st_size} bytes to {output_file}"
                )
            else:
                logger.warning(f"No data in response for {date_str}")

        except (httpx.HTTPError, Exception) as e:
            logger.error(f"Failed to scrape {date_str}: {e}")

    logger.info(f"Completed scraping {day_count} days")


def read_scrape(output: Path) -> list[dict[str, Any]]:
    """
    Read all scraped JSON files from the output directory.

    Loads and parses all JSON files from the specified directory,
    sorting them by date to ensure chronological processing.

    Args:
        output: Directory containing the scraped JSON files

    Returns:
        list[dict]: List of parsed JSON data from all files
    """
    logger.debug(f"Reading scraped files from {output}")
    data = []
    files = list(output.glob("*.json"))
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
