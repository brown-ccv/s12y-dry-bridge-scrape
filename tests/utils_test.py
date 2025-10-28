from datetime import datetime
from unittest import TestCase

from dry_bridge.utils import round_down_15min


class TestUtils(TestCase):
    def test_round_down_15min(self):
        timestamp = datetime(2025, 2, 3, 4, 56, 7, 8910)
        self.assertEqual(round_down_15min(timestamp), datetime(2025, 2, 3, 4, 45, 0, 0))
