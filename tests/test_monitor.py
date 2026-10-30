"""Compatibility checks for the package metrics API."""
import unittest
from netwatch.monitor import Result, summarize


class SummaryTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(summarize([])["availability_pct"], 0.0)

    def test_mixed(self):
        samples = [
            Result("", "test", "tcp", "localhost", 80, True, 10.0),
            Result("", "test", "tcp", "localhost", 80, False, None),
            Result("", "test", "tcp", "localhost", 80, True, 20.0),
        ]
        stats = summarize(samples)
        self.assertEqual(stats["avg_ms"], 15.0)
        self.assertEqual(stats["availability_pct"], 66.67)


if __name__ == "__main__":
    unittest.main()
