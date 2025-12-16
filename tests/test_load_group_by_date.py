import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from dry_bridge.load import group_by_date


class TestGroupByDate(unittest.TestCase):
    """Test the group_by_date deduplication and timezone preservation logic."""

    def test_empty_list(self):
        """Test empty input returns empty output."""
        result = group_by_date([])
        self.assertEqual(len(result), 0)

    def test_preserves_timezone(self):
        """Test that timezone from input timestamps is preserved."""
        tz = ZoneInfo("America/New_York")
        timestamps = [
            datetime(2023, 8, 1, 10, 15, tzinfo=tz),
            datetime(2023, 8, 2, 14, 30, tzinfo=tz),
        ]
        result = group_by_date(timestamps)
        
        for dt in result:
            self.assertEqual(dt.tzinfo, tz)

    def test_deduplicates_same_date(self):
        """Test that multiple timestamps on same date produce single result."""
        tz = ZoneInfo("America/New_York")
        timestamps = [
            datetime(2023, 8, 1, 0, 0, tzinfo=tz),
            datetime(2023, 8, 1, 6, 0, tzinfo=tz),
            datetime(2023, 8, 1, 12, 0, tzinfo=tz),
            datetime(2023, 8, 1, 23, 59, tzinfo=tz),
        ]
        result = group_by_date(timestamps)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].date(), datetime(2023, 8, 1).date())

    def test_sets_midnight_time(self):
        """Test that result timestamps are at midnight."""
        tz = ZoneInfo("America/New_York")
        timestamps = [
            datetime(2023, 8, 1, 14, 30, tzinfo=tz),
            datetime(2023, 8, 2, 9, 45, tzinfo=tz),
        ]
        result = group_by_date(timestamps)
        
        for dt in result:
            self.assertEqual(dt.hour, 0)
            self.assertEqual(dt.minute, 0)
            self.assertEqual(dt.second, 0)
            self.assertEqual(dt.microsecond, 0)

    def test_sorts_output(self):
        """Test that output is sorted by date."""
        tz = ZoneInfo("America/New_York")
        timestamps = [
            datetime(2023, 8, 5, 10, 0, tzinfo=tz),
            datetime(2023, 8, 1, 10, 0, tzinfo=tz),
            datetime(2023, 8, 3, 10, 0, tzinfo=tz),
        ]
        result = group_by_date(timestamps)
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].date(), datetime(2023, 8, 1).date())
        self.assertEqual(result[1].date(), datetime(2023, 8, 3).date())
        self.assertEqual(result[2].date(), datetime(2023, 8, 5).date())


if __name__ == "__main__":
    unittest.main()
