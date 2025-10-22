from datetime import datetime
from unittest import TestCase
from unittest.mock import patch
from zoneinfo import ZoneInfo

from dry_bridge.utils import days_from_timestamp, round_down_15min


class TestUtils(TestCase):
    @patch("dry_bridge.utils.datetime")
    def test_days_from_timestamp(self, dt_mock):
        tz = ZoneInfo("America/New_York")
        timestamp = datetime(2025, 12, 23)
        dt_mock.now.return_value = datetime(2025, 12, 25)

        self.assertEqual(
            days_from_timestamp(timestamp),
            [
                datetime(2025, 12, 23, tzinfo=tz),
                datetime(2025, 12, 24, tzinfo=tz),
                datetime(2025, 12, 25, tzinfo=tz),
            ],
        )

    def test_round_down_15min(self):
        timestamp = datetime(2025, 2, 3, 4, 56, 7, 8910)
        self.assertEqual(round_down_15min(timestamp), datetime(2025, 2, 3, 4, 45, 0, 0))
