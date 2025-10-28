import unittest
from pathlib import Path

from dry_bridge.scrape import read_scrape_file
from dry_bridge.transform import flatten_raw_data, RawRow


class TestTransform(unittest.TestCase):
    def test_flatten_raw_data(self):
        data = read_scrape_file(Path(__file__).parent / "data" / "sample_input.json")
        expected_rows = [
            RawRow(
                name="L0 - Production Meter 1 (Pad 1)",
                timestamp="2023-10-31T00:00:00",
                type="column",
                units="Kilowatts",
                value=-15.848,
            ),
            RawRow(
                name="L0 - Production Meter 1 (Pad 1)",
                timestamp="2023-10-31T00:15:00",
                type="column",
                units="Kilowatts",
                value=-15.9647,
            ),
            RawRow(
                name="SEL-735 SPARE PARTS 3",
                timestamp="2023-10-31T00:00:00",
                type="column",
                units="Kilowatts",
                value=None,
            ),
            RawRow(
                name="SEL-735 SPARE PARTS 3",
                timestamp="2023-10-31T00:15:00",
                type="column",
                units="Kilowatts",
                value=None,
            ),
        ]
        self.assertEqual(
            sorted(expected_rows, key=lambda x: x.timestamp),
            sorted(flatten_raw_data(data), key=lambda x: x.timestamp),
        )
