import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
START_OF_OPERATION = datetime(2023, 9, 9, tzinfo=ZoneInfo("America/New_York"))


def round_down_15min(timestamp: datetime) -> datetime:
    minutes_past_hour = timestamp.minute
    remainder_minutes = minutes_past_hour % 15
    delta = timedelta(minutes=remainder_minutes)
    return (timestamp - delta).replace(second=0, microsecond=0)


def local_now() -> datetime:
    tz = ZoneInfo("America/New_York")
    return datetime.now().astimezone(tz)


def iso_to_local(timestamp: str) -> datetime:
    tz = ZoneInfo("America/New_York")
    naive = datetime.fromisoformat(timestamp)
    return naive.replace(tzinfo=tz)


def remove_future_timestamps(
    now: datetime, timestamps: list[datetime], buffer_minutes: int = 3
) -> list[datetime]:
    nearest_15 = round_down_15min(now)
    buffered_time = nearest_15 - timedelta(minutes=buffer_minutes)
    return list(filter(lambda x: x <= buffered_time, timestamps))
