import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dry_bridge.load import group_by_date
from dry_bridge.utils import START_OF_OPERATION, round_down_15min


class TestGroupByDate(unittest.TestCase):
    def test_single_date(self):
        """Test grouping timestamps from single date."""
        timestamps = [
            datetime(2023, 8, 1, 0, 0),
            datetime(2023, 8, 1, 0, 15),
            datetime(2023, 8, 1, 0, 30),
        ]
        result = group_by_date(timestamps)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], datetime(2023, 8, 1, 0, 0))

    def test_multiple_dates(self):
        """Test grouping timestamps from multiple dates."""
        timestamps = [
            datetime(2023, 8, 1, 0, 0),
            datetime(2023, 8, 1, 0, 15),
            datetime(2023, 8, 2, 0, 0),
            datetime(2023, 8, 3, 12, 30),
        ]
        result = group_by_date(timestamps)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], datetime(2023, 8, 1, 0, 0))
        self.assertEqual(result[1], datetime(2023, 8, 2, 0, 0))
        self.assertEqual(result[2], datetime(2023, 8, 3, 0, 0))

    def test_empty_list(self):
        """Test grouping empty timestamp list."""
        result = group_by_date([])
        self.assertEqual(len(result), 0)

    def test_unsorted_timestamps(self):
        """Test that result is sorted even with unsorted input."""
        timestamps = [
            datetime(2023, 8, 3, 12, 30),
            datetime(2023, 8, 1, 0, 15),
            datetime(2023, 8, 2, 0, 0),
        ]
        result = group_by_date(timestamps)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], datetime(2023, 8, 1, 0, 0))
        self.assertEqual(result[1], datetime(2023, 8, 2, 0, 0))
        self.assertEqual(result[2], datetime(2023, 8, 3, 0, 0))


class TestTimestampGeneration(unittest.TestCase):
    def test_15_minute_intervals(self):
        """Test that we generate correct 15-minute intervals."""
        timestamps = []
        current = START_OF_OPERATION
        delta = timedelta(minutes=15)

        for _ in range(4):
            timestamps.append(current)
            current += delta

        self.assertEqual(timestamps[0].minute, 0)
        self.assertEqual(timestamps[1].minute, 15)
        self.assertEqual(timestamps[2].minute, 30)
        self.assertEqual(timestamps[3].minute, 45)

    def test_round_down_15min(self):
        """Test rounding down to 15-minute intervals."""
        test_time = datetime(
            2023, 8, 1, 10, 17, 30, tzinfo=ZoneInfo("America/New_York")
        )
        rounded = round_down_15min(test_time)
        self.assertEqual(rounded.minute, 15)
        self.assertEqual(rounded.second, 0)

        test_time = datetime(
            2023, 8, 1, 10, 44, 59, tzinfo=ZoneInfo("America/New_York")
        )
        rounded = round_down_15min(test_time)
        self.assertEqual(rounded.minute, 30)
        self.assertEqual(rounded.second, 0)
