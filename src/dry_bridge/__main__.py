import logging
import os
from datetime import datetime
from itertools import chain
from pathlib import Path

import typer
from dotenv import load_dotenv
from typing_extensions import Annotated

from .scrape import scrape, read_scrape
from .load import DatabaseConfig, database_connection, load_raw, load_transformed
from .transform import flatten_raw_data, transform_raw_data


app = typer.Typer()

load_dotenv()

START_OF_OPERATION = datetime(2023, 7, 1)

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
):
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
):
    try:
        db_config = DatabaseConfig(
            host=os.environ["DB_HOST"],
            port=int(os.environ["DB_PORT"]),
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )
    except KeyError:
        raise Exception("invalid database configuration, double check your environment")

    conn = database_connection(db_config)
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
def realtime():
    pass


def main():
    app()
