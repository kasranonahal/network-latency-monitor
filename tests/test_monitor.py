import unittest
from monitor import summarize


class SummaryTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(summarize([])["success_rate"], 0.0)

    def test_mixed(self):
        stats = summarize([{"latency_ms": 10.0}, {"latency_ms": None}, {"latency_ms": 20.0}])
        self.assertEqual(stats["avg_ms"], 15.0)
        self.assertEqual(stats["success_rate"], 66.7)


if __name__ == "__main__":
    unittest.main()
