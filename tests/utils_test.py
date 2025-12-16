from datetime import datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from dry_bridge.utils import round_down_15min, remove_future_timestamps, iso_to_local


class TestRoundDown15Min(TestCase):
    def test_round_down_basic(self):
        """Test basic rounding to 15-minute intervals."""
        timestamp = datetime(2025, 2, 3, 4, 56, 7, 8910)
        self.assertEqual(round_down_15min(timestamp), datetime(2025, 2, 3, 4, 45, 0, 0))

    def test_round_down_already_on_boundary(self):
        """Test timestamp already on 15-min boundary stays unchanged."""
        timestamp = datetime(2025, 2, 3, 4, 30, 0, 0)
        self.assertEqual(round_down_15min(timestamp), datetime(2025, 2, 3, 4, 30, 0, 0))

    def test_round_down_clears_seconds_and_micros(self):
        """Test that seconds and microseconds are zeroed out."""
        timestamp = datetime(2025, 2, 3, 4, 17, 59, 999999)
        result = round_down_15min(timestamp)
        self.assertEqual(result.minute, 15)
        self.assertEqual(result.second, 0)
        self.assertEqual(result.microsecond, 0)

    def test_round_down_all_intervals(self):
        """Test rounding for all 15-min intervals in an hour."""
        # 0-14 mins -> 0
        self.assertEqual(round_down_15min(datetime(2025, 1, 1, 1, 7)).minute, 0)
        # 15-29 mins -> 15
        self.assertEqual(round_down_15min(datetime(2025, 1, 1, 1, 22)).minute, 15)
        # 30-44 mins -> 30
        self.assertEqual(round_down_15min(datetime(2025, 1, 1, 1, 38)).minute, 30)
        # 45-59 mins -> 45
        self.assertEqual(round_down_15min(datetime(2025, 1, 1, 1, 59)).minute, 45)


class TestRemoveFutureTimestamps(TestCase):
    def test_remove_future_with_buffer(self):
        """Test filtering: now=2:33 -> rounds to 2:30 -> buffer 3min = 2:27."""
        now = datetime(2025, 12, 10, 2, 33)
        timestamps = [
            datetime(2025, 12, 10, 2, 15),
            datetime(2025, 12, 10, 2, 30),
            datetime(2025, 12, 10, 2, 45),
        ]
        result = remove_future_timestamps(now, timestamps)
        self.assertEqual(1, len(result))
        self.assertEqual(result[0], datetime(2025, 12, 10, 2, 15))

    def test_remove_future_custom_buffer(self):
        """Test with custom buffer size."""
        now = datetime(2025, 12, 10, 2, 33)
        timestamps = [
            datetime(2025, 12, 10, 2, 0),
            datetime(2025, 12, 10, 2, 15),
            datetime(2025, 12, 10, 2, 30),
        ]
        # 2:33 -> 2:30 -> buffer 15min = 2:15
        result = remove_future_timestamps(now, timestamps, buffer_minutes=15)
        self.assertEqual(2, len(result))
        self.assertIn(datetime(2025, 12, 10, 2, 0), result)
        self.assertIn(datetime(2025, 12, 10, 2, 15), result)

    def test_remove_future_boundary_inclusive(self):
        """Test that timestamps exactly at buffer time are included (<=)."""
        now = datetime(2025, 12, 10, 2, 33)  # -> 2:30 -> buffer = 2:27
        timestamps = [datetime(2025, 12, 10, 2, 27)]
        result = remove_future_timestamps(now, timestamps)
        self.assertEqual(1, len(result))

    def test_remove_future_all_dropped(self):
        """Test when all timestamps are beyond buffer."""
        now = datetime(2025, 12, 10, 2, 5)  # -> 2:00 -> buffer = 1:57
        timestamps = [
            datetime(2025, 12, 10, 2, 0),
            datetime(2025, 12, 10, 2, 15),
        ]
        result = remove_future_timestamps(now, timestamps)
        self.assertEqual(0, len(result))

    def test_remove_future_empty_input(self):
        """Test with empty timestamp list."""
        now = datetime(2025, 12, 10, 2, 33)
        result = remove_future_timestamps(now, [])
        self.assertEqual(0, len(result))


class TestIsoToLocal(TestCase):
    def test_iso_to_local_no_time_shift(self):
        """Test that iso_to_local adds timezone without shifting time values."""
        result = iso_to_local("2024-01-15T09:45:30")
        self.assertEqual(result.hour, 9)
        self.assertEqual(result.minute, 45)
        self.assertEqual(result.second, 30)
        self.assertEqual(result.tzinfo, ZoneInfo("America/New_York"))
