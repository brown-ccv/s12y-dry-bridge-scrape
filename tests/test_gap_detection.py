import unittest
from datetime import datetime, timedelta
from dry_bridge.load import compute_missing_timestamps


class TestComputeMissingTimestamps(unittest.TestCase):
    def test_empty_existing_timestamps(self):
        """When no timestamps exist, all should be missing."""
        existing = set()
        start = datetime(2024, 1, 1, 0, 0)
        end = datetime(2024, 1, 1, 1, 0)
        
        result = compute_missing_timestamps(existing, start, end)
        
        # Should have 5 timestamps: 00:00, 00:15, 00:30, 00:45, 01:00
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], datetime(2024, 1, 1, 0, 0))
        self.assertEqual(result[1], datetime(2024, 1, 1, 0, 15))
        self.assertEqual(result[4], datetime(2024, 1, 1, 1, 0))

    def test_gap_in_middle(self):
        """Missing timestamp in middle should be detected."""
        start = datetime(2024, 1, 1, 0, 0)
        
        # Existing: 00:00, 00:15, 00:45 (missing 00:30)
        existing = {
            datetime(2024, 1, 1, 0, 0),
            datetime(2024, 1, 1, 0, 15),
            datetime(2024, 1, 1, 0, 45),
        }
        end = datetime(2024, 1, 1, 0, 45)
        
        result = compute_missing_timestamps(existing, start, end)
        
        # Should find only the 00:30 gap
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], datetime(2024, 1, 1, 0, 30))

    def test_multiple_gaps(self):
        """Multiple missing timestamps should all be detected."""
        start = datetime(2024, 1, 1, 0, 0)
        
        # Existing: only 00:00 and 01:00 (missing 00:15, 00:30, 00:45)
        existing = {
            datetime(2024, 1, 1, 0, 0),
            datetime(2024, 1, 1, 1, 0),
        }
        end = datetime(2024, 1, 1, 1, 0)
        
        result = compute_missing_timestamps(existing, start, end)
        
        # Should find 3 gaps
        self.assertEqual(len(result), 3)
        self.assertIn(datetime(2024, 1, 1, 0, 15), result)
        self.assertIn(datetime(2024, 1, 1, 0, 30), result)
        self.assertIn(datetime(2024, 1, 1, 0, 45), result)

    def test_complete_data(self):
        """When all timestamps exist, none should be missing."""
        start = datetime(2024, 1, 1, 0, 0)
        end = datetime(2024, 1, 1, 1, 0)
        
        # Create complete set
        existing = set()
        current = start
        delta = timedelta(minutes=15)
        while current <= end:
            existing.add(current)
            current += delta
        
        result = compute_missing_timestamps(existing, start, end)
        
        # Should find no gaps
        self.assertEqual(len(result), 0)

    def test_result_is_sorted(self):
        """Result should be sorted even if existing set is not."""
        start = datetime(2024, 1, 1, 0, 0)
        end = datetime(2024, 1, 1, 1, 0)
        
        # Add timestamps in random order
        existing = {
            datetime(2024, 1, 1, 0, 45),
            datetime(2024, 1, 1, 0, 0),
        }
        
        result = compute_missing_timestamps(existing, start, end)
        
        # Result should be sorted
        self.assertEqual(result, sorted(result))


if __name__ == '__main__':
    unittest.main()
