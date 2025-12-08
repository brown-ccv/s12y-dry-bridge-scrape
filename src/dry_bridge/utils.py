import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
START_OF_OPERATION = datetime(2023, 9, 9, tzinfo=ZoneInfo("America/New_York"))
MAX_FETCH_ATTEMPTS = int(os.getenv("MAX_FETCH_ATTEMPTS", "5"))


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
    return datetime.fromisoformat(timestamp).astimezone(tz)
