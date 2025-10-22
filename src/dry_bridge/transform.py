from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class RawRow:
    name: str
    timestamp: str
    type: str
    units: str
    value: float | None


@dataclass(frozen=True)
class ProcessedRow:
    kw: float | None
    kwh: float | None
    mmbtu: float | None
    mtco2e: float | None
    timestamp: datetime


def process_inverter_data(timestamp: str, kw: float | None) -> ProcessedRow:
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
    return [
        process_inverter_data(d.timestamp, d.value)
        for d in data
        if "Inverter" in d.name
    ]


def flatten_raw_data(raw: dict[str, Any]) -> list[RawRow]:
    data = []
    for x in raw["data"]:
        name = str(x["name"])
        units = str(x["units"])
        type = str(x["type"])
        for y in x["data"]:
            row = RawRow(
                name=name,
                timestamp=y[0],
                type=type,
                units=units,
                value=y[1],
            )
            data.append(row)
    return data


def raw_to_processed(raw: RawRow) -> ProcessedRow:
    return process_inverter_data(raw.timestamp, raw.value)


def local_to_utc(timestamp: str) -> datetime:
    naive_timestamp = datetime.fromisoformat(timestamp)
    local_timetimestamp = naive_timestamp.replace(tzinfo=ZoneInfo("America/New_York"))
    return local_timetimestamp.astimezone(ZoneInfo("UTC"))
