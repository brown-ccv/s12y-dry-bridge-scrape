from datetime import datetime
from unittest import TestCase

from dry_bridge.utils import round_down_15min, remove_future_timestamps


class TestUtils(TestCase):
    def test_round_down_15min(self):
        timestamp = datetime(2025, 2, 3, 4, 56, 7, 8910)
        self.assertEqual(round_down_15min(timestamp), datetime(2025, 2, 3, 4, 45, 0, 0))

    def test_remove_future_timestamps(self):
        now = datetime(2025, 12, 10, 2, 33)
        timestamps = [
            datetime(2025, 12, 10, 2, 15),
            datetime(2025, 12, 10, 2, 30),
            datetime(2025, 12, 10, 2, 45),
        ]
        self.assertEqual(2, len(remove_future_timestamps(now, timestamps)))
