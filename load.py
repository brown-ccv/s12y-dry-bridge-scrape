#!/usr/bin/env python3
import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
from psycopg2 import Error
from dotenv import load_dotenv

load_dotenv()

DATE_FORMAT = "%Y-%M-%d"

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


@dataclass
class DataPoint:
    timestamp: datetime
    value: float

    @staticmethod
    def load(date_str: str, value: float):
        timestamp = datetime.fromisoformat(date_str)
        return DataPoint(timestamp=timestamp, value=value)


@dataclass
class DataFrame:
    data: list[DataPoint]
    name: str
    units: str

    @staticmethod
    def load(json: dict[str, Any]):
        name = json["name"]
        units = json["units"]
        data = [DataPoint.load(d[0], d[1]) for d in json["data"]]
        return DataFrame(name=name, units=units, data=data)


@dataclass
class DataFile:
    data: list[DataFrame]

    @staticmethod
    def load(json: dict[str, Any]):
        data = [DataFrame.load(d) for d in json["data"]]
        return DataFile(data=data)


def get_db_connection():
    try:
        connection = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
        )
        return connection
    except Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None


def create_tables(connection):
    try:
        cursor = connection.cursor()

        create_table_query = """
        CREATE TABLE IF NOT EXISTS raw_drybridge_data (
            timestamp TIMESTAMP PRIMARY KEY,
            pad1 FLOAT,
            pad2 FLOAT,
            pad3 FLOAT,
            pad4 FLOAT,
            spare_parts2,
            spare_parts3,
            spare_parts4,
            spare_parts5,
            inverters
        );
        CREATE TABLE IF NOT EXISTS processed_drybridge_data (
            timestamp TIMESTAMP PRIMARY KEY,
            kw FLOAT,
            kwh FLOAT,
            mmbtu FLOAT,
            mtco2e FLOAT
        );
        """
        cursor.execute(create_table_query)
        connection.commit()
        cursor.close()
    except Error as e:
        print(f"Error managing table: {e}")


def process_inverter_data(timestamp, kw):
    kwh = kw * 0.25
    mmbtu = kwh * 0.003412
    mtco2e = (
        (kwh * 0.0002369153)
        + (kwh * 0.0000000371952 * 28)
        + (kwh * 0.0000000049896 * 265)
    )

    return {
        "timestamp": timestamp,
        "kw": kw,
        "kwh": kwh,
        "mmbtu": mmbtu,
        "mtco2e": mtco2e,
    }


def insert_solar_data(connection, csv_path):
    df = pd.read_csv(csv_path, parse_dates=[0])

    data_to_insert = []
    for _, row in df.iterrows():
        timestamp = row[df.columns[0]]
        if pd.isna(timestamp):
            print(f"Skipping row with invalid timestamp: {row}")
            continue

        inverter_value = row["Inverters"]
        if pd.isna(inverter_value):
            print(f"Skipping row with invalid inverter value: {row}")
            continue

        metrics = process_inverter_data(timestamp, inverter_value)
        data_to_insert.append(
            (
                metrics["timestamp"],
                metrics["kw"],
                metrics["kwh"],
                metrics["mmbtu"],
                metrics["mtco2e"],
            )
        )

    if not data_to_insert:
        print("No valid data to insert")
        return

    cursor = connection.cursor()
    cursor.executemany(
        """
        INSERT INTO solar_production 
        (timestamp, kw, kwh, mmbtu, mtco2e)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (timestamp) 
        DO UPDATE SET 
            kw = EXCLUDED.kw,
            kwh = EXCLUDED.kwh,
            mmbtu = EXCLUDED.mmbtu,
            mtco2e = EXCLUDED.mtco2e;
    """,
        data_to_insert,
    )

    connection.commit()
    cursor.close()
    print("Successfully inserted data")


def find_last_start(connection):
    cursor = connection.cursor()
    cursor.execute("""
        SELECT
            timestamp from solar_production
        ORDER BY
            timestamp DESC
        LIMIT 1;  
    """)

    try:
        timestamp = cursor.fetchone()[0]
        return timestamp
    except TypeError:
        return None


def run(playwright, time_range, **kwargs):
    browser = playwright.chromium.launch(headless=False)
    connection = get_db_connection()
    resume = kwargs.get("resume")
    start = kwargs.get("start")
    end = kwargs.get("end")

    try:
        if connection:
            create_tables(connection)

        last_start = find_last_start(connection)

        if start and resume and last_start:
            scrape_range(browser, last_start, end, connection)
        elif start:
            scrape_range(browser, start, end, connection)
        else:
            scrape_page(browser, time_range, connection)

    finally:
        if connection:
            connection.close()
        browser.close()


def scrape_page(browser, time_range, connection):
    page = browser.new_page()
    page.goto(
        "https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US"
    )
    page.wait_for_timeout(1000)
    range_selector = page.locator(f"#date-range-button-{time_range}")
    range_selector.click()
    button = page.locator(".highcharts-contextbutton")
    button.click()
    menu = page.get_by_text("Download CSV")
    with page.expect_download() as download_info:
        menu.click()
    download = download_info.value
    csv_path = f"./chart-{time_range}.csv"
    download.save_as(csv_path)

    if connection:
        insert_solar_data(connection, csv_path)

    browser.close()


def scrape_range(browser, start, end, connection):
    end = datetime.now() if end == None else end
    page = browser.new_page()
    page.goto(
        "https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US"
    )
    page.wait_for_timeout(3000)
    range_selector = page.locator("#date-range-button-day")
    range_selector.click()
    page.wait_for_timeout(3000)

    # For tracking status of download/insertion
    day_status = {
        "success": [],
        "failed_download": [],
        "failed_insert": [],
    }

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 5000

    for day in daterange(start, end):
        current_date_text = page.locator("#date-range-dialog-selector").text_content()
        current_date = datetime.strptime(
            current_date_text.split("-")[0].strip(), "%b %d, %Y"
        )
        while current_date.strftime(DATE_FORMAT) != day.strftime(DATE_FORMAT):
            if current_date < day:
                page.locator("#date-time-picker-button-right-arrow").click()
            else:
                page.locator("#date-time-picker-button-left-arrow").click()
            page.wait_for_timeout(3000)
            current_date_text = page.locator(
                "#date-range-dialog-selector"
            ).text_content()
            current_date = datetime.strptime(
                current_date_text.split("-")[0].strip(), "%b %d, %Y"
            )

        download_success = False
        # Sometimes download fails, so allow 3 retries
        for attempt in range(MAX_RETRIES):
            try:
                button = page.locator(".highcharts-contextbutton")
                button.click(timeout=1000)

                menu = page.get_by_text("Download CSV")
                with page.expect_download() as download_info:
                    menu.click(timeout=1000)
                download = download_info.value

                csv_path = f"./chart-{day.strftime('%Y-%m-%d')}.csv"
                download.save_as(csv_path)

                with open(csv_path, "r") as f:
                    csv_content = f.read()

                download_success = True
                # Successfully downloaded, exit
                break

            except TimeoutError:
                print(
                    f"Attempt {attempt + 1}/{MAX_RETRIES} failed to download CSV for {day.strftime(DATE_FORMAT)}"
                )
                if attempt < MAX_RETRIES - 1:
                    print(f"Waiting {RETRY_DELAY / 1000} seconds before retrying...")
                    page.wait_for_timeout(RETRY_DELAY)
                continue

        if not download_success:
            print(
                f"All {MAX_RETRIES} attempts failed to download CSV for {day.strftime(DATE_FORMAT)}"
            )
            day_status["failed_download"].append(day.strftime(DATE_FORMAT))
            continue

        # If download was successful, try to insert data
        if connection:
            try:
                insert_solar_data(connection, csv_path)
                day_status["success"].append(day.strftime(DATE_FORMAT))
            except Exception as e:
                print(f"Failed to insert data for {day.strftime(DATE_FORMAT)}: {e}")
                day_status["failed_insert"].append(day.strftime(DATE_FORMAT))
        else:
            day_status["success"].append(day.strftime(DATE_FORMAT))

    print("\nScraping Summary:")
    print(f"Successfully processed: {len(day_status['success'])} days")
    if day_status["success"]:
        print("Successful days:", ", ".join(day_status["success"]))
    if day_status["failed_download"]:
        print("Failed to download CSV:", ", ".join(day_status["failed_download"]))
    if day_status["failed_insert"]:
        print("Failed to insert data:", ", ".join(day_status["failed_insert"]))

    browser.close()


def daterange(start_date, end_date):
    days = int((end_date - start_date).days) + 1
    for n in range(days):
        yield end_date - timedelta(n)


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d")


def load_data(input_dir: Path) -> None:
    print(input_dir)
    for fname in input_dir.glob("*.json"):
        if "metadata" == fname.stem:
            continue

        df = pd.read_json(fname)

        print(df, [d for d in df.data])

        break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="load raw dry bridge solar data into postgres"
    )
    parser.add_argument(
        "-d",
        dest="dir",
        type=Path,
        help="input directory",
        default=Path().cwd() / "output",
    )
    parser.add_argument("-s", dest="start", type=parse_date, help="start date")
    parser.add_argument("-e", dest="end", type=parse_date, help="end date")
    args = parser.parse_args()
    load_data(args.dir)


if __name__ == "__main__":
    main()
