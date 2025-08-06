#!/usr/bin/env python3
import argparse
import httpx
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from dotenv import load_dotenv
from httpx_retries import RetryTransport, Retry
from pathlib import Path

START_OF_OPERATION = datetime(2023, 1, 1)

load_dotenv()

logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.CRITICAL,
)

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


@dataclass
class Metadata:
    """
    metadata of the downloads for the raw data
    """

    path: Path
    last_start: datetime | None
    success: list[str]
    failed: list[str]

    def save(self):
        """save data to disk"""
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
        """load metadata from disk"""
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


def run(
    start: datetime,
    end: datetime | None,
    resume: bool,
    output: Path,
):
    """
    loads up the different arguments and kicks off the scrape
    """
    end = datetime.now() if not end else end
    output = Path("output") if not output else output

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
    this function is responsible for downloading all the CSV files and updating metadata
    """
    home_url = "https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US"
    api_url = "https://hmi.alsoenergy.com/api/view/sourcedata/C44014"
    retry = Retry(total=MAX_RETRIES, backoff_factor=0.5)
    client = httpx.Client(transport=RetryTransport(retry=retry))

    # NOTE(@broarr): This is to get the auth cookies only
    result = client.get(home_url, follow_redirects=True)

    print(f"start: {start}, end: {end}")
    current_date = start
    while current_date < end:
        metadata.last_start = current_date
        print(current_date.strftime("%Y-%m-%d"))
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


def daterange(start_date: datetime, end_date: datetime):
    """
    generator function to find the next day in the list
    """
    days = int((end_date - start_date).days) + 1
    for n in range(days):
        yield end_date - timedelta(n)


def main():
    """
    handle the argument parsing and setup of playwright
    """
    parser = argparse.ArgumentParser(description="scrape dry bridge solar data")
    parser.add_argument(
        "-c", dest="resume", action="store_true", help="continue previous scan"
    )
    parser.add_argument(
        "-e", dest="end", type=datetime.fromisoformat, help="end date", required=False
    )
    parser.add_argument(
        "-o",
        dest="output",
        type=Path,
        help="output directory",
        default="output",
    )

    start_time_group = parser.add_mutually_exclusive_group(required=True)
    start_time_group.add_argument(
        "-a", dest="all", action="store_true", help="get all historical data"
    )
    start_time_group.add_argument(
        "-s",
        dest="start",
        type=datetime.fromisoformat,
        help="start date",
    )

    args = parser.parse_args()
    run(
        start=args.start if not args.all else START_OF_OPERATION,
        end=args.end,
        resume=args.resume,
        output=args.output,
    )


if __name__ == "__main__":
    main()
