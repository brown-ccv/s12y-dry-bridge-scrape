"""
Data transformation module for solar production data.

This module handles the transformation of raw solar production data from the
dashboard API into structured formats suitable for analysis and storage.
It includes timezone conversion, unit calculations, and data flattening operations.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawRow:
    """
    Raw data row from the solar dashboard API.

    Represents a single measurement from the solar monitoring system,
    containing metadata about the measurement and its value.
    """

    name: str  # Name/identifier of the measurement source (e.g., "Inverter")
    timestamp: str  # ISO format timestamp string in local time
    type: str  # Type of measurement
    units: str  # Units of measurement (e.g., "kW", "kWh")
    value: float | None  # Numeric value of the measurement, or None if unavailable


@dataclass(frozen=True)
class ProcessedRow:
    """
    Processed solar production data row.

    Contains calculated values for various energy metrics derived from
    raw power measurements, with timestamps converted to UTC.
    """

    kw: float | None  # Power in kilowatts
    kwh: (
        float | None
    )  # Energy in kilowatt-hours (calculated from kW * 0.25 for 15-min intervals)
    mmbtu: float | None  # Energy in million British thermal units
    mtco2e: float | None  # Carbon dioxide equivalent in metric tons avoided
    timestamp: datetime  # UTC timestamp for the measurement


def process_inverter_data(timestamp: str, kw: float | None) -> ProcessedRow:
    """
    Process raw inverter power data into standardized metrics.

    Converts raw power measurements into energy and environmental impact metrics,
    handling timezone conversion and applying standard conversion factors.

    Args:
        timestamp: ISO format timestamp string in Eastern time
        kw: Power measurement in kilowatts, or None if unavailable

    Returns:
        ProcessedRow: Processed data with calculated energy and environmental metrics
    """
    # NOTE(@broarr): We need to convert the timestamps from eastern local time to
    #   UTC to account for things like daylight savings time
    utc_timestamp = local_to_utc(timestamp)

    if kw is None:
        # TODO(@broarr): Is this the right thing to do? We'll have to clear it with Derek
        return ProcessedRow(
            timestamp=utc_timestamp,
            kw=None,
            kwh=None,
            mmbtu=None,
            mtco2e=None,
        )

    kwh = kw * 0.25
    mmbtu = kwh * 0.003412
    mtco2e = (
        (kwh * 0.0002369153)
        + (kwh * 0.0000000371952 * 28)
        + (kwh * 0.0000000049896 * 265)
    )

    return ProcessedRow(
        timestamp=utc_timestamp,
        kw=kw,
        kwh=kwh,
        mmbtu=mmbtu,
        mtco2e=mtco2e,
    )


def transform_raw_data(data: list[RawRow]) -> list[ProcessedRow]:
    """
    Transform a list of raw data rows into processed rows.

    Filters for inverter data and processes each measurement into standardized
    energy and environmental metrics.

    Args:
        data: List of raw data rows from the solar monitoring system

    Returns:
        list[ProcessedRow]: List of processed rows with calculated metrics
    """
    logger.debug(f"Transforming {len(data)} raw data rows")
    inverter_data = [d for d in data if "Inverter" in d.name]
    logger.debug(f"Found {len(inverter_data)} inverter data rows to process")

    processed = [process_inverter_data(d.timestamp, d.value) for d in inverter_data]

    logger.info(f"Transformed {len(processed)} raw rows into processed data")
    return processed


def flatten_raw_data(raw: dict[str, Any]) -> list[RawRow]:
    """
    Flatten nested JSON response into individual data rows.

    Converts the hierarchical JSON structure from the dashboard API into
    a flat list of individual measurements for easier processing.

    Args:
        raw: Raw JSON response from the dashboard API

    Returns:
        list[RawRow]: Flattened list of individual measurement rows
    """
    logger.debug(
        f"Flattening raw data with {len(raw.get('data', []))} top-level entries"
    )
    data = []
    for x in raw["data"]:
        name = str(x["name"])
        units = str(x["units"])
        type = str(x["type"])
        logger.debug(
            f"Processing {name} ({type}, {units}) with {len(x['data'])} data points"
        )

        for y in x["data"]:
            row = RawRow(
                name=name,
                timestamp=y[0],
                type=type,
                units=units,
                value=y[1],
            )
            data.append(row)

    logger.debug(f"Flattened into {len(data)} total data rows")
    return data


def raw_to_processed(raw: RawRow) -> ProcessedRow:
    """
    Convert a single raw data row to a processed row.

    Args:
        raw: Raw data row to process

    Returns:
        ProcessedRow: Processed data with calculated metrics
    """
    return process_inverter_data(raw.timestamp, raw.value)


def local_to_utc(timestamp: str) -> datetime:
    """
    Convert local Eastern time timestamp to UTC.

    Handles timezone conversion including daylight saving time transitions
    by explicitly setting the timezone to America/New_York before converting to UTC.

    Args:
        timestamp: ISO format timestamp string in local Eastern time

    Returns:
        datetime: UTC datetime object
    """
    naive_timestamp = datetime.fromisoformat(timestamp)
    local_timetimestamp = naive_timestamp.replace(tzinfo=ZoneInfo("America/New_York"))
    return local_timetimestamp.astimezone(ZoneInfo("UTC"))
