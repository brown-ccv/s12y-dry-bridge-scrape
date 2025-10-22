"""
Web scraping module for extracting solar production data.

This module handles the extraction of solar production data from the Dry Bridge
solar farm dashboard. It manages authentication, retry logic, and data persistence
for reliable data collection across date ranges.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from httpx_retries import RetryTransport, Retry


MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))


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

    def save(self):
        """
        Save metadata to disk as JSON.

        Persists the current state of the scraping metadata to enable
        resuming interrupted scrapes and tracking download history.
        """
        with open(self.path, "w") as f:
            date_str = self.last_start.strftime("%Y-%m-%d") if self.last_start else None
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
    def load(path: Path):
        """
        Load metadata from disk or create new instance if file doesn't exist.

        Args:
            path: Path to the metadata JSON file

        Returns:
            Metadata: Loaded metadata instance or new empty instance
        """
        try:
            with open(path, "r") as f:
                j = json.loads(f.read())
                return Metadata(
                    last_start=j["last_start"],
                    success=j["success"],
                    failed=j["failed"],
                    path=path,
                )
        except FileNotFoundError:
            return Metadata(last_start=None, success=[], failed=[], path=path)


def scrape(
    start: datetime,
    end: datetime,
    resume: bool,
    output: Path,
):
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
    if not output.exists():
        output.mkdir()

    metadata = Metadata.load(Path(output) / "metadata.json")
    last_start = metadata.last_start

    if start and resume and last_start:
        metadata = scrape_range(last_start, end, output, metadata)
    else:
        metadata = scrape_range(start, end, output, metadata)

    metadata.save()


def scrape_range(
    start: datetime, end: datetime, output: Path, metadata: Metadata
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
    home_url = "https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US"
    api_url = "https://hmi.alsoenergy.com/api/view/sourcedata/C44014"
    retry = Retry(total=MAX_RETRIES, backoff_factor=0.5)
    client = httpx.Client(transport=RetryTransport(retry=retry))

    # NOTE(@broarr): This is to get the auth cookies only
    result = client.get(home_url, follow_redirects=True)

    current_date = start
    while current_date < end:
        metadata.last_start = current_date
        date_str = current_date.strftime("%Y-%m-%d")
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
        headers = {"Referer": home_url}
        try:
            result = client.post(
                api_url, headers=headers, json=req_params, timeout=10.0
            )
            data = result.json()

            if len(data["data"]) > 0:
                metadata.success.append(date_str)
                with open(output / f"{date_str}.json", "w") as f:
                    f.write(json.dumps(data, indent=2, sort_keys=True))
            else:
                raise Exception(f"no data in response body for date {date_str}")
        except (httpx.HTTPError, Exception):
            metadata.failed.append(date_str)
        current_date += timedelta(days=1)

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
    data = []
    files = [f for f in output.glob("*.json") if "metadata" not in f.name]
    files = sorted(files, key=lambda f: datetime.fromisoformat(f.stem))
    for f in files:
        data.append(read_scrape_file(f))
    return data


def read_scrape_file(fname: Path) -> dict[str, Any]:
    """
    Read and parse a single scraped JSON file.

    Args:
        fname: Path to the JSON file to read

    Returns:
        dict: Parsed JSON data from the file
    """
    return json.loads(fname.read_text())
