from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

START_OF_OPERATION = datetime(2023, 7, 1)


def days_from_timestamp(timestamp: datetime) -> list[datetime]:
    # NOTE(@broarr): We need to move things into local time from
    #   UTC to make sure we query for the right stuff
    tz = ZoneInfo("America/New_York")
    local_now = datetime.now().astimezone(tz)
    local_current = timestamp.astimezone(tz)
    delta = timedelta(days=1)
    print(local_now, local_current, local_current < local_now)

    dates = []
    while local_current <= local_now:
        dates.append(local_current)
        local_current += delta

    return dates


def round_down_15min(timestamp: datetime) -> datetime:
    minutes_past_hour = timestamp.minute
    remainder_minutes = minutes_past_hour % 15
    delta = timedelta(minutes=remainder_minutes)
    return (timestamp - delta).replace(second=0, microsecond=0)


def local_now() -> datetime:
    tz = ZoneInfo("America/New_York")
    return datetime.now().astimezone(tz)
